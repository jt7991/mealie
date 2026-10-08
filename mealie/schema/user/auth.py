from typing import Annotated

from fastapi import Form
from pydantic import UUID4, BaseModel, StringConstraints

from mealie.schema._mealie.mealie_model import MealieModel


class Token(BaseModel):
    access_token: str
    token_type: str


class MagicLinkRequest(BaseModel):
    email: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"),
    ]


class MagicLinkVerify(BaseModel):
    token: Annotated[str, StringConstraints(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")]
    remember_me: bool = True


class TokenData(BaseModel):
    user_id: UUID4 | None = None
    username: Annotated[str, StringConstraints(to_lower=True, strip_whitespace=True)] | None = None  # type: ignore


class UnlockResults(MealieModel):
    unlocked: int = 0


class CredentialsRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class OIDCNativeConfig(BaseModel):
    """Parameters a native client needs to start an OIDC authorization request itself."""

    authorization_endpoint: str
    client_id: str
    scope: str


class NativeOIDCTokenRequest(BaseModel):
    """An authorization code captured by a native client, for server-side exchange."""

    code: str
    code_verifier: str
    redirect_uri: str
    nonce: str | None = None


class CredentialsRequestForm:
    """Class that represents a user's credentials from the login form"""

    def __init__(
        self,
        username: str = Form(""),
        password: str = Form(""),
        remember_me: bool = Form(False),
    ):
        self.username = username
        self.password = password
        self.remember_me = remember_me
