import uvicorn
from geoalchemy2.elements import WKTElement
from pydantic import Field
from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict
from sqlmodel import Session, select, text

from help_matcher.auth import hash_password
from help_matcher.database import engine
from help_matcher.models import Demand, DemandUser, OAuthIdentity, OAuthProvider, Offer, OfferUser, User, UserRole, utc_now
from help_matcher.tags import link_tags


class ServeSettings(BaseSettings):
    """Run the Help Matcher FastAPI server."""

    host: str = Field(default="0.0.0.0", description="Host interface to bind.")
    port: int = Field(default=8000, description="Port to bind.")
    reload: bool = Field(default=False, description="Reload the server when code changes.")
    log_level: str = Field(default="info", description="Uvicorn log level.")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SERVER_",
        cli_parse_args=True,
        cli_prog_name="serve",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_show_env_vars=True,
        extra="ignore",
    )

    def cli_cmd(self) -> None:
        uvicorn.run(
            "help_matcher.main:app",
            host=self.host,
            port=self.port,
            reload=self.reload,
            log_level=self.log_level,
        )


def serve() -> None:
    CliApp.run(ServeSettings)


class CreateAdminSettings(BaseSettings):
    """Create or update an admin user."""

    username: str = Field(description="Admin username.")
    password: str = Field(description="Admin password.")
    name: str | None = Field(default=None, description="Optional display name.")
    update_existing: bool = Field(default=False, description="Update password/name if the admin already exists.")

    model_config = SettingsConfigDict(
        env_file=".env",
        cli_parse_args=True,
        cli_prog_name="create_admin",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        extra="ignore",
    )

    def cli_cmd(self) -> None:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.username == self.username)).first()
            if user is not None and not self.update_existing:
                raise SystemExit(
                    f"Admin username '{self.username}' already exists. "
                    "Use --update-existing to update the password."
                )
            if user is None:
                user = User(username=self.username, role=UserRole.admin)
                action = "Created"
            else:
                action = "Updated"

            user.password_hash = hash_password(self.password)
            user.role = UserRole.admin
            if self.name is not None:
                user.name = self.name
            user.updated_at = utc_now()
            session.add(user)
            session.commit()
            session.refresh(user)
            identity = session.exec(
                select(OAuthIdentity).where(
                    OAuthIdentity.provider == OAuthProvider.local,
                    OAuthIdentity.subject == self.username,
                )
            ).first()
            if identity is None:
                session.add(OAuthIdentity(user_id=user.id, provider=OAuthProvider.local, subject=self.username))
                session.commit()

        print(f"{action} admin user '{self.username}'.")


def create_admin() -> None:
    CliApp.run(CreateAdminSettings)


class LoadSampleDataSettings(BaseSettings):
    """Load sample offers and demands for local UI testing."""

    clear_existing: bool = Field(default=False, description="Delete previously loaded sample records first.")

    model_config = SettingsConfigDict(
        env_file=".env",
        cli_parse_args=True,
        cli_prog_name="load_sample_data",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        extra="ignore",
    )

    def cli_cmd(self) -> None:
        sample_username = "sample-data"
        with Session(engine) as session:
            user = session.exec(select(User).where(User.username == sample_username)).first()
            if user is None:
                user = User(
                    name="Sample Data",
                    username=sample_username,
                    whatsapp_bsuid="sample-data",
                )
                session.add(user)
                session.commit()
                session.refresh(user)

            if self.clear_existing:
                session.exec(text("DELETE FROM offertag WHERE offer_id IN (SELECT offer_id FROM offeruser JOIN \"user\" ON \"user\".id = offeruser.user_id WHERE \"user\".username LIKE 'sample-data-%')"))
                session.exec(text("DELETE FROM demandtag WHERE demand_id IN (SELECT demand_id FROM demanduser JOIN \"user\" ON \"user\".id = demanduser.user_id WHERE \"user\".username LIKE 'sample-data-%')"))
                session.exec(text("""
                    WITH target AS (
                        SELECT offer_id AS id
                        FROM offeruser
                        JOIN "user" ON "user".id = offeruser.user_id
                        WHERE "user".username LIKE 'sample-data-%'
                    ),
                    deleted_links AS (
                        DELETE FROM offeruser WHERE offer_id IN (SELECT id FROM target)
                    )
                    DELETE FROM offer WHERE id IN (SELECT id FROM target)
                """))
                session.exec(text("""
                    WITH target AS (
                        SELECT demand_id AS id
                        FROM demanduser
                        JOIN "user" ON "user".id = demanduser.user_id
                        WHERE "user".username LIKE 'sample-data-%'
                    ),
                    deleted_links AS (
                        DELETE FROM demanduser WHERE demand_id IN (SELECT id FROM target)
                    )
                    DELETE FROM demand WHERE id IN (SELECT id FROM target)
                """))
                session.exec(text("DELETE FROM \"user\" WHERE username LIKE 'sample-data-%'"))
                session.commit()

            if session.exec(text("SELECT 1 FROM \"user\" WHERE username LIKE 'sample-data-%' LIMIT 1")).first() is not None:
                print("Sample data already exists. Use --clear-existing to reload it.")
                return

            def sample_contact(key: str, name: str, phone_number: str) -> User:
                contact = User(username=f"sample-data-{key}", name=name, phone_number=phone_number)
                session.add(contact)
                session.commit()
                session.refresh(contact)
                return contact

            contacts = {
                "maquinaria": sample_contact("maquinaria", "Contacto maquinaria", "+57 300 000 0001"),
                "olla": sample_contact("olla", "Coordinacion olla comunitaria", "+57 300 000 0002"),
                "acopio": sample_contact("acopio", "Coordinador de ayuda", "+57 300 000 0003"),
                "marta": sample_contact("marta", "Marta", "+57 300 000 0004"),
                "sorangela": sample_contact("sorangela", "Sorangela", "+57 300 000 0005"),
                "david": sample_contact("david", "David Mejia", "+57 300 000 0006"),
                "vanessa": sample_contact("vanessa", "Punto de acopio Edificio Vanessa", "+57 300 000 0007"),
                "jonathan": sample_contact("jonathan", "Jonathan Wilches", "+57 300 000 0008"),
                "libardo": sample_contact("libardo", "Sr. Libardo", "+57 300 000 0009"),
                "limonar": sample_contact("limonar", "Contacto Torres de Limonar Capri", "+57 300 000 0010"),
            }

            offers = [
                (
                    Offer(
                        title="Maquinaria pesada disponible en Cali",
                        original_message=(
                            "Apoyo solidario Cali: maquinaria pesada disponible para enviar a cualquier punto "
                            "de Cali para remoción de escombros."
                        ),
                        administrative_area_name="Cali",
                        administrative_area_level="municipality",
                        address_text="Cali",
                        geometry=WKTElement("POINT(-76.5320 3.4516)", srid=4326),
                    ),
                    ["maquinaria", "escombros", "rescate"],
                    [contacts["maquinaria"]],
                ),
                (
                    Offer(
                        title="Olla comunitaria en El Limonar",
                        original_message=(
                            "Ayuda comunitaria: olla comunitaria en Cali para vecinos de El Limonar, "
                            "Cuarto de Legua, La Cascada y El Refugio. Sin gas, cocinando con lena."
                        ),
                        administrative_area_name="El Limonar",
                        administrative_area_level="locality",
                        address_text="Cruce Calle 62 con Carrera Tercera, al lado de Universidad Santiago de Cali",
                        geometry=WKTElement("POINT(-76.5450 3.4074)", srid=4326),
                    ),
                    ["comida", "olla comunitaria", "vecinos"],
                    [contacts["olla"]],
                ),
                (
                    Offer(
                        title="Punto de acopio para rescatistas",
                        original_message=(
                            "Punto de acopio y apoyo a rescatistas y movedores de escombros en Barrio "
                            "Carrera 60 con Calle 4; se solicitan desayunos preparados, bebidas hidratantes, "
                            "agua potable y snacks energeticos."
                        ),
                        administrative_area_name="Barrio Carrera 60 con Calle 4",
                        administrative_area_level="locality",
                        address_text="Carrera 60 con Calle 4, Cali",
                        geometry=WKTElement("POINT(-76.5470 3.4215)", srid=4326),
                    ),
                    ["agua", "comida", "hidratacion", "rescatistas"],
                    [contacts["acopio"]],
                ),
            ]
            demands = [
                (
                    Demand(
                        title="Ancianato necesita panales, agua y alimentos",
                        original_message=(
                            "Ancianato de las Hermanitas de los Pobres junto a dona Maria Isabel necesita "
                            "panales talla M en adelante, panitos, crema panalitis, agua, alimentos no "
                            "perecederos y manitos colaboradoras para remover escombros."
                        ),
                        administrative_area_name="Cali",
                        administrative_area_level="locality",
                        address_text="Ancianato de las Hermanitas de los Pobres, Cali",
                        geometry=WKTElement("POINT(-76.5319 3.4516)", srid=4326),
                    ),
                    ["panales", "agua", "alimentos", "escombros"],
                    [contacts["marta"], contacts["sorangela"]],
                ),
                (
                    Demand(
                        title="Edificio Vanessa necesita apoyo logistico",
                        original_message=(
                            "Requerimiento logistico urgente en Edificio Vanessa, Calle 9 con 44: "
                            "2 volquetas de escombros, sistema de comunicacion digital, 5 megafonos "
                            "y chalecos reflectivos."
                        ),
                        administrative_area_name="Edificio Vanessa",
                        administrative_area_level="locality",
                        address_text="Calle 9 con 44, Cali",
                        geometry=WKTElement("POINT(-76.5402 3.4225)", srid=4326),
                    ),
                    ["volquetas", "comunicacion", "megafonos", "chalecos"],
                    [contacts["david"]],
                ),
                (
                    Demand(
                        title="Rescate urgente en Edificio Vanessa",
                        original_message=(
                            "Requerimiento urgente para rescate de personas con vida bajo escombros en "
                            "Edificio Vanessa, Calle 9 con 44: herramientas de construccion, cascos, "
                            "equipo de proteccion, comunicadores punto a punto, vacunas antitetanicas, "
                            "hidratacion sin azucar y bebidas energizantes."
                        ),
                        administrative_area_name="Edificio Vanessa",
                        administrative_area_level="locality",
                        address_text="Calle 9 con 44, Cali",
                        geometry=WKTElement("POINT(-76.5402 3.4225)", srid=4326),
                    ),
                    ["rescate", "herramientas", "proteccion", "radios", "vacunas", "hidratacion"],
                    [contacts["vanessa"]],
                ),
                (
                    Demand(
                        title="Edificio Cantabria necesita radios",
                        original_message=(
                            "Requerimiento urgente en Edificio Cantabria, Calle 8b con 46, Barrio Nueva "
                            "Tequendama: 8 radios punto a punto para personas con vida."
                        ),
                        administrative_area_name="Nueva Tequendama",
                        administrative_area_level="barrio",
                        address_text="Edificio Cantabria, Calle 8b con 46, Cali",
                        geometry=WKTElement("POINT(-76.5427 3.4205)", srid=4326),
                    ),
                    ["radios", "comunicacion", "rescate"],
                    [contacts["jonathan"]],
                ),
                (
                    Demand(
                        title="12 familias sin casa en La Paz",
                        original_message=(
                            "12 familias perdieron sus casas en el corregimiento de La Paz y necesitan "
                            "apoyo urgente y coordinacion de ayudas."
                        ),
                        administrative_area_name="La Paz",
                        administrative_area_level="corregimiento",
                        address_text="Corregimiento de La Paz, Cali",
                        geometry=WKTElement("POINT(-76.5857 3.5090)", srid=4326),
                    ),
                    ["vivienda", "familias", "ayuda urgente"],
                    [contacts["libardo"]],
                ),
                (
                    Demand(
                        title="Senales de vida en Torres de Limonar Capri",
                        original_message=(
                            "Torres de Limonar Capri reporta 3 senales claras de vida y espera apoyo "
                            "de maquinaria para rescate."
                        ),
                        administrative_area_name="Torres de Limonar Capri",
                        administrative_area_level="building",
                        address_text="Torres de Limonar Capri, Cali",
                        geometry=WKTElement("POINT(-76.5485 3.4037)", srid=4326),
                    ),
                    ["rescate", "maquinaria", "vida bajo escombros"],
                    [contacts["limonar"]],
                ),
            ]

            for record, tags, record_contacts in [*offers, *demands]:
                session.add(record)
                session.commit()
                session.refresh(record)
                for contact in record_contacts:
                    if isinstance(record, Offer):
                        session.add(OfferUser(offer_id=record.id, user_id=contact.id))
                    else:
                        session.add(DemandUser(demand_id=record.id, user_id=contact.id))
                session.commit()
                session.refresh(record)
                link_tags(session, record, tags)

        print(f"Loaded {len(offers)} sample offers and {len(demands)} sample demands.")


def load_sample_data() -> None:
    CliApp.run(LoadSampleDataSettings)
