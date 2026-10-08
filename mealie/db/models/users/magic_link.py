from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._model_utils.datetime import NaiveDateTime
from mealie.db.models._model_utils.guid import GUID


class MagicLinkModel(SqlAlchemyBase):
    __tablename__ = "magic_link_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    requester_hash: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[UUID | None] = mapped_column(GUID, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    credential_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(NaiveDateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(NaiveDateTime)
