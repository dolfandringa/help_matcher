import hmac
from hashlib import sha256

from help_matcher.webhooks import verify_meta_signature


def test_verify_meta_signature_accepts_valid_signature() -> None:
    body = b'{"entry":[]}'
    secret = "test-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, sha256).hexdigest()

    verify_meta_signature(body, signature, secret)

