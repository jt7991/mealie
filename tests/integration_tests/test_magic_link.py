import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import delete, select

from mealie.core.config import get_app_settings
from mealie.db.db_setup import session_context
from mealie.db.models.users.magic_link import MagicLinkModel
from mealie.db.models.users.users import AuthMethod, User
from mealie.repos.repository_magic_links import RepositoryMagicLinks
from mealie.services.email import EmailService

REQUEST = "/api/auth/magic-link"
VERIFY = f"{REQUEST}/verify"


@pytest.fixture
def magic_email(monkeypatch, session):
    settings = get_app_settings()
    for name, value in {
        "MAGIC_LINK_ENABLED": True,
        "SMTP_HOST": "smtp.resend.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "resend",
        "SMTP_PASSWORD": "test-only-key",
        "SMTP_AUTH_STRATEGY": "SSL",
        "SMTP_FROM_EMAIL": "recipes@example.com",
        "SMTP_FROM_NAME": "Mealie",
        "BASE_URL": "https://mealie.example.com",
        "TOKEN_TIME": 8760,
    }.items():
        monkeypatch.setattr(settings, name, value)
    session.execute(delete(MagicLinkModel))
    session.commit()
    messages = []

    def send(_self, email, url):
        messages.append((email, url))
        return True

    monkeypatch.setattr(EmailService, "send_magic_link", send)
    yield messages
    session.execute(delete(MagicLinkModel))
    session.commit()


def request_token(client, user, messages):
    response = client.post(REQUEST, json={"email": user.email.upper()})
    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    assert messages[-1][0] == user.email
    assert messages[-1][1].startswith("https://mealie.example.com/login#magic=")
    return messages[-1][1].split("#magic=")[1]


def test_link_is_hashed_single_use_and_remembers_for_one_year(api_client, unique_user_fn_scoped, magic_email, session):
    user = unique_user_fn_scoped
    token = request_token(api_client, user, magic_email)
    row = session.scalar(select(MagicLinkModel))
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(row.__dict__)
    response = api_client.post(VERIFY, json={"token": token, "remember_me": True})
    assert response.status_code == 200
    assert response.json()["expires_in"] == 365 * 24 * 3600
    assert "Max-Age=31536000" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    claims = jwt.decode(response.json()["access_token"], get_app_settings().SECRET, algorithms=["HS256"])
    assert claims["sub"] == str(user.user_id)
    assert claims["rme"] is True
    assert api_client.get("/api/users/self").json()["id"] == str(user.user_id)
    assert api_client.post(VERIFY, json={"token": token}).status_code == 401


def test_unremembered_login_uses_session_cookie(api_client, unique_user_fn_scoped, magic_email):
    token = request_token(api_client, unique_user_fn_scoped, magic_email)
    response = api_client.post(VERIFY, json={"token": token, "remember_me": False})
    assert response.status_code == 200
    assert "Max-Age" not in response.headers["set-cookie"]


def test_unknown_account_and_throttled_account_get_same_response(api_client, unique_user_fn_scoped, magic_email):
    known = api_client.post(REQUEST, json={"email": unique_user_fn_scoped.email})
    repeated = api_client.post(REQUEST, json={"email": unique_user_fn_scoped.email})
    unknown = api_client.post(REQUEST, json={"email": "unknown@example.com"})
    assert known.status_code == repeated.status_code == unknown.status_code == 202
    assert known.json() == repeated.json() == unknown.json()
    assert len(magic_email) == 1


def test_expired_link_rejected(api_client, unique_user_fn_scoped, magic_email, session):
    token = request_token(api_client, unique_user_fn_scoped, magic_email)
    row = session.scalar(select(MagicLinkModel))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    response = api_client.post(VERIFY, json={"token": token})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("change", ["email", "password", "locked", "attempts", "method", "revoked"])
def test_account_changes_invalidate_link(api_client, unique_user_fn_scoped, magic_email, session, change):
    user = unique_user_fn_scoped
    token = request_token(api_client, user, magic_email)
    row = session.get(User, user.user_id)
    if change == "email":
        row.email = "changed@example.com"
    elif change == "password":
        row.password = "changed-hash"
    elif change == "locked":
        row.locked_at = datetime.now(UTC)
    elif change == "attempts":
        row.login_attemps = get_app_settings().SECURITY_MAX_LOGIN_ATTEMPTS
    elif change == "method":
        row.auth_method = AuthMethod.OIDC
    else:
        row.tokens_valid_after = datetime.now(UTC)
    session.commit()
    response = api_client.post(VERIFY, json={"token": token})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("method", [AuthMethod.LDAP, AuthMethod.OIDC])
def test_external_accounts_cannot_use_email_login(api_client, unique_user_fn_scoped, magic_email, session, method):
    session.get(User, unique_user_fn_scoped.user_id).auth_method = method
    session.commit()
    response = api_client.post(REQUEST, json={"email": unique_user_fn_scoped.email})
    assert response.status_code == 202
    assert magic_email == []


def test_only_one_concurrent_consumer_wins(api_client, unique_user_fn_scoped, magic_email):
    token = request_token(api_client, unique_user_fn_scoped, magic_email)
    digest = hashlib.sha256(token.encode()).hexdigest()

    def consume(_):
        with session_context() as session:
            return RepositoryMagicLinks(session).consume(digest, datetime.now(UTC))

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(consume, range(2))) == [False, True]


def test_failed_delivery_invalidates_token(api_client, unique_user_fn_scoped, magic_email, monkeypatch, session):
    monkeypatch.setattr(EmailService, "send_magic_link", lambda *_: False)
    response = api_client.post(REQUEST, json={"email": unique_user_fn_scoped.email})
    assert response.status_code == 202
    session.expire_all()
    assert session.scalar(select(MagicLinkModel)).consumed_at is not None


def test_feature_disabled_without_email_credentials(api_client, magic_email, monkeypatch):
    monkeypatch.setattr(get_app_settings(), "SMTP_PASSWORD", None)
    assert not api_client.get("/api/app/about").json()["enableMagicLink"]
    assert api_client.post(REQUEST, json={"email": "user@example.com"}).status_code == 503
    assert api_client.post(VERIFY, json={"token": "a" * 43}).status_code == 503


def test_ip_rate_limit_includes_unknown_accounts(api_client, magic_email, session):
    for index in range(25):
        assert api_client.post(REQUEST, json={"email": f"unknown{index}@example.com"}).status_code == 202
    assert len(list(session.scalars(select(MagicLinkModel)))) == 20


def test_get_does_not_consume_link(api_client, unique_user_fn_scoped, magic_email, session):
    token = request_token(api_client, unique_user_fn_scoped, magic_email)
    assert api_client.get(VERIFY, params={"token": token}).status_code == 405
    session.expire_all()
    assert session.scalar(select(MagicLinkModel)).consumed_at is None
