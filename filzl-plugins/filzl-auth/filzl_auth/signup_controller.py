from typing import Type

from fastapi import Depends
from filzl.actions import passthrough
from filzl.controller import ControllerBase
from filzl.database.dependencies import DatabaseDependencies
from filzl.dependencies import CoreDependencies
from filzl.exceptions import APIException
from filzl.paths import ManagedViewPath
from filzl.render import Metadata, RenderBase
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from filzl_auth.config import AuthConfig
from filzl_auth.user_model import User
from filzl_auth.views import get_auth_view_path


class SignupRender(RenderBase):
    recapcha_enabled: bool
    recapcha_client_key: str | None


class SignupRequest(BaseModel):
    username: EmailStr
    password: str
    recapcha_key: str | None


class SignupInvalid(APIException):
    status_code = 401
    invalid_reason: str


class SignupController(ControllerBase):
    url = "/auth/signup"
    view_path = (
        ManagedViewPath.from_view_root(get_auth_view_path(""), package_root_link=None)
        / "auth/signup/page.tsx"
    )

    def __init__(self, user_model: Type[User] = User):
        super().__init__()
        self.user_model = user_model

    def render(
        self,
        auth_config: AuthConfig = Depends(
            CoreDependencies.get_config_with_type(AuthConfig)
        ),
    ) -> SignupRender:
        return SignupRender(
            recapcha_enabled=auth_config.RECAPTCHA_ENABLED,
            recapcha_client_key=auth_config.RECAPTCHA_GCP_CLIENT_KEY,
            metadata=Metadata(title="Signup"),
        )

    @passthrough(exception_models=[SignupInvalid])
    def signup(
        self,
        signup_payload: SignupRequest,
        auth_config: AuthConfig = Depends(
            CoreDependencies.get_config_with_type(AuthConfig)
        ),
        session: Session = Depends(DatabaseDependencies.get_db_session),
    ):
        # If recapcha is enabled, we require the key
        if auth_config.RECAPTCHA_ENABLED and signup_payload.recapcha_key is None:
            raise SignupInvalid(invalid_reason="Recapcha is required.")

        matched_users = select(self.user_model).where(
            self.user_model.email == signup_payload.username
        )
        user = session.exec(matched_users).first()
        if user is not None:
            raise SignupInvalid(invalid_reason="User already exists with this email.")

        # Create a new user
        hashed_password = self.user_model.get_password_hash(signup_payload.password)

        new_user = self.user_model(
            email=signup_payload.username, hashed_password=hashed_password
        )
        session.add(new_user)
        session.commit()

        # Successful login
        raise SignupInvalid(invalid_reason="Signup successful!")
