import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from mealie.core.security.tokens import create_access_token
from mealie.db.db_setup import session_context
from mealie.db.models.users.magic_link import MagicLinkModel
from mealie.db.models.users.users import AuthMethod
from mealie.repos.all_repositories import get_repositories
from mealie.schema.user.user import PrivateUser
from mealie.services._base_service import BaseService
from mealie.services.email import EmailService

MAGIC_LINK_LIFETIME = timedelta(minutes=15)


class MagicLinkService(BaseService):
    def __init__(self, session: Session) -> None:
        super().__init__()
        repos = get_repositories(session, group_id=None, household_id=None)
        self.users = repos.users
        self.tokens = repos.magic_links

    def digest(self, purpose: str, value: str) -> str:
        return hmac.new(self.settings.SECRET.encode(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()

    def credentials_digest(self, user: PrivateUser) -> str:
        return self.digest("credentials", f"{user.password}:{user.tokens_valid_after}")

    def eligible(self, user: PrivateUser | None) -> bool:
        return bool(
            user
            and user.auth_method == AuthMethod.MEALIE
            and not user.is_locked
            and user.login_attemps < self.settings.SECURITY_MAX_LOGIN_ATTEMPTS
        )

    def request_link(self, email: str, requester: str) -> tuple[str, str] | None:
        """Store the same throttling record for both known and unknown addresses."""
        now = datetime.now(UTC)
        normalized = email.strip().lower()
        user = self.users.get_one(normalized, "email", any_case=True)
        if not self.eligible(user):
            user = None
        token = secrets.token_urlsafe(32)
        challenge = MagicLinkModel(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            request_key=self.digest("request", f"{normalized}:{int(now.timestamp()) // 60}"),
            email_hash=self.digest("email", normalized),
            requester_hash=self.digest("requester", requester),
            user_id=user.id if user else None,
            credential_hash=self.credentials_digest(user) if user else None,
            created_at=now,
            expires_at=now + MAGIC_LINK_LIFETIME,
        )
        if not self.tokens.create_limited(challenge, now) or not user:
            return None
        return user.email, token

    def verify(self, token: str, remember_me: bool) -> tuple[str, timedelta] | None:
        now = datetime.now(UTC)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        challenge = self.tokens.get(token_hash)
        if not challenge or challenge.consumed_at or challenge.expires_at <= now or not challenge.user_id:
            return None
        user = self.users.get_one(challenge.user_id)
        if not self.eligible(user) or not user:
            return None
        if not hmac.compare_digest(challenge.email_hash, self.digest("email", user.email.strip().lower())):
            return None
        if not hmac.compare_digest(challenge.credential_hash or "", self.credentials_digest(user)):
            return None
        if not self.tokens.consume(token_hash, now):
            return None
        return create_access_token({"sub": str(user.id), "rme": remember_me})


def deliver_magic_link(email: str, token: str, locale: str | None) -> None:
    """Send after the generic response; never log the address, link, or SMTP exception."""
    email_service = EmailService(locale=locale)
    # Fragments are not sent in HTTP requests, access logs, or Referer headers.
    url = f"{email_service.settings.BASE_URL}/login#magic={token}"
    try:
        if email_service.send_magic_link(email, url):
            email_service.logger.info("Magic-link email accepted by the email provider")
            return
    except Exception:
        pass
    email_service.logger.error("Magic-link email delivery failed; check the email provider configuration")
    with session_context() as session:
        repos = get_repositories(session, group_id=None, household_id=None)
        repos.magic_links.consume(hashlib.sha256(token.encode()).hexdigest(), datetime.now(UTC))
