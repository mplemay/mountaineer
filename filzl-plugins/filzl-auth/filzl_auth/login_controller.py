from typing import Type

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse
from filzl.actions import passthrough
from filzl.controller import ControllerBase
from filzl.database.dependencies import DatabaseDependencies
from filzl.dependencies import CoreDependencies, get_function_dependencies
from filzl.exceptions import APIException
from filzl.paths import ManagedViewPath
from filzl.render import Metadata, RedirectStatus, RenderBase
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from filzl_auth.authorize import authorize_response
from filzl_auth.config import AuthConfig
from filzl_auth.dependencies import AuthDependencies
from filzl_auth.user_model import User
from filzl_auth.views import get_auth_view_path


class LoginRequest(BaseModel):
    username: EmailStr
    password: str


class LoginSuccessResponse(BaseModel):
    redirect_url: str


class LoginInvalid(APIException):
    status_code = 401
    invalid_reason: str


class LoginController(ControllerBase):
    """
    Clients can override this login controller to instantiate their own login / view conventions.
    """

    url = "/auth/login"
    view_path = (
        ManagedViewPath.from_view_root(get_auth_view_path(""), package_root_link=None)
        / "auth/login/page.tsx"
    )

    # Defaults to 24 hours
    token_expiration_minutes: int = 60 * 24

    def __init__(
        self,
        post_login_redirect: str,
        user_model: Type[User] = User,
    ):
        super().__init__()
        self.user_model = user_model
        self.post_login_redirect = post_login_redirect

    async def render(
        self,
        request: Request,
    ) -> RenderBase:
        # Workaround to provide user-defined models into the dependency layer
        get_dependencies_fn = AuthDependencies.peek_user(self.user_model)
        async with get_function_dependencies(
            callable=get_dependencies_fn, url=self.url, request=request
        ) as values:
            user = get_dependencies_fn(**values)

        if user is not None:
            # return RedirectResponse(url=self.post_login_redirect, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
            return RenderBase(
                metadata=Metadata(
                    redirect=RedirectStatus(
                        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                        url=self.post_login_redirect,
                    )
                )
            )

        # Otherwise continue to load the initial page
        return RenderBase(
            metadata=Metadata(
                title="Login",
            )
        )

    @passthrough(exception_models=[LoginInvalid], response_model=LoginSuccessResponse)
    async def login(
        self,
        login_payload: LoginRequest,
        auth_config: AuthConfig = Depends(
            CoreDependencies.get_config_with_type(AuthConfig)
        ),
        session: AsyncSession = Depends(DatabaseDependencies.get_db_session),
    ):
        matched_users = select(self.user_model).where(
            self.user_model.email == login_payload.username
        )
        results = await session.execute(matched_users)
        user = results.scalars().first()
        if user is None:
            raise LoginInvalid(invalid_reason="User not found.")
        if not user.verify_password(login_payload.password):
            raise LoginInvalid(invalid_reason="Invalid password.")

        payload = LoginSuccessResponse(redirect_url=self.post_login_redirect)

        response = JSONResponse(
            content=payload.model_dump_json(), status_code=status.HTTP_200_OK
        )
        response = authorize_response(
            response,
            user_id=user.id,
            auth_config=auth_config,
            token_expiration_minutes=self.token_expiration_minutes,
        )

        return response
