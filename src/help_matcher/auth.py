from datetime import timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from help_matcher.config import get_settings
from help_matcher.database import get_session
from help_matcher.models import (
    AdminCreate,
    LoginRequest,
    OAuthIdentity,
    OAuthIdentityCreate,
    OAuthLoginRequest,
    OAuthProvider,
    TokenRead,
    User,
    UserRole,
    utc_now,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/form")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user: User) -> str:
    settings = get_settings()
    expires_at = utc_now() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "username": user.username,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def token_for_user(user: User) -> TokenRead:
    return TokenRead(access_token=create_access_token(user), user=user)


def authenticate_admin(session: Session, *, username: str, password: str) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or user.role != UserRole.admin or user.password_hash is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    """Resolve the current user from an OAuth2 bearer access token."""

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from None

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user = session.get(User, int(subject))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require an authenticated OAuth2 bearer token for an admin user."""

    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.post("/admins", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
def create_admin(payload: AdminCreate, session: Session = Depends(get_session)) -> TokenRead:
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(
        username=payload.username,
        name=payload.name,
        role=UserRole.admin,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(OAuthIdentity(user_id=user.id, provider=OAuthProvider.local, subject=payload.username))
    session.commit()
    session.refresh(user)
    return token_for_user(user)


@router.post("/login", response_model=TokenRead)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenRead:
    return token_for_user(authenticate_admin(session, username=payload.username, password=payload.password))


@router.post("/login/form", response_model=TokenRead)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenRead:
    return token_for_user(authenticate_admin(session, username=form_data.username, password=form_data.password))


@router.post("/oauth-identities", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
def record_oauth_identity(payload: OAuthIdentityCreate, session: Session = Depends(get_session)) -> TokenRead:
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can use backend OAuth login")

    existing = session.exec(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == payload.provider,
            OAuthIdentity.subject == payload.subject,
        )
    ).first()
    if existing is not None and existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="OAuth identity already linked")
    if existing is None:
        identity = OAuthIdentity.model_validate(payload)
        session.add(identity)
    else:
        existing.email = payload.email or existing.email
        existing.updated_at = utc_now()
        session.add(existing)
    session.commit()
    session.refresh(user)
    return token_for_user(user)


@router.post("/oauth-token", response_model=TokenRead)
def oauth_login(payload: OAuthLoginRequest, session: Session = Depends(get_session)) -> TokenRead:
    identity = session.exec(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == payload.provider,
            OAuthIdentity.subject == payload.subject,
        )
    ).first()
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown OAuth identity")
    user = session.get(User, identity.user_id)
    if user is None or user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown OAuth identity")
    return token_for_user(user)
