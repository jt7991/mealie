from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mealie.db.models.users.magic_link import MagicLinkModel


class RepositoryMagicLinks:
    """Authentication challenges are global, before a group or household is known."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_limited(self, challenge: MagicLinkModel, now: datetime) -> bool:
        # Keep request records for rate limits even after use or failed delivery.
        self.session.execute(delete(MagicLinkModel).where(MagicLinkModel.created_at < now - timedelta(days=1)))
        recent = MagicLinkModel.created_at > now - timedelta(minutes=15)
        email_count = self.session.scalar(
            select(func.count())
            .select_from(MagicLinkModel)
            .where(recent, MagicLinkModel.email_hash == challenge.email_hash)
        )
        ip_count = self.session.scalar(
            select(func.count())
            .select_from(MagicLinkModel)
            .where(recent, MagicLinkModel.requester_hash == challenge.requester_hash)
        )
        cooldown = self.session.scalar(
            select(MagicLinkModel.id)
            .where(
                MagicLinkModel.email_hash == challenge.email_hash,
                MagicLinkModel.created_at > now - timedelta(minutes=1),
            )
            .limit(1)
        )
        if cooldown is not None or (email_count or 0) >= 5 or (ip_count or 0) >= 20:
            self.session.commit()
            return False
        self.session.add(challenge)
        try:
            self.session.commit()
        except IntegrityError:
            # A unique per-email, per-minute key also arbitrates concurrent requests.
            self.session.rollback()
            return False
        return True

    def get(self, token_hash: str) -> MagicLinkModel | None:
        return self.session.scalar(select(MagicLinkModel).where(MagicLinkModel.token_hash == token_hash))

    def consume(self, token_hash: str, now: datetime) -> bool:
        # A single conditional UPDATE prevents two workers redeeming the same link.
        consumed = self.session.execute(
            update(MagicLinkModel)
            .where(
                MagicLinkModel.token_hash == token_hash,
                MagicLinkModel.consumed_at.is_(None),
                MagicLinkModel.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(MagicLinkModel.id)
        ).scalar_one_or_none()
        self.session.commit()
        return consumed is not None
