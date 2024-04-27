import re
from typing import cast
from urllib.parse import unquote

import aiohttp
import aiohttp.client_exceptions
import tortoise
import tortoise.exceptions
from litestar import Controller, Litestar, Request, get, post
from litestar.connection import ASGIConnection
from litestar.datastructures import State
from litestar.exceptions import NotAuthorizedException, ValidationException
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
from litestar.middleware.base import DefineMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.engine.url import URL
from tortoise import Tortoise, connections

from syncious.database import VideosTable
from syncious.env import SETTINGS

YOUTUBE_ID_REGEX = r"[a-zA-Z0-9_-]{11}"

YOUTUBE_ID_REGEX_COMPLIED = re.compile(YOUTUBE_ID_REGEX)


class BasicAuthMiddleware(AbstractAuthenticationMiddleware):
    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        authorization = connection.headers.get("Authorization")

        if not authorization or not authorization.startswith(("Bearer ", "bearer ")):
            raise NotAuthorizedException()

        token = authorization.removeprefix("Bearer ").removeprefix("bearer ")

        http = cast(aiohttp.ClientSession, connection.app.state.http)

        # Lets not rewrite how Invidious validates tokens

        try:
            resp = await http.get(
                f"{SETTINGS.invidious_instance}/api/v1/auth/feed",
                headers={"Authorization": f"Bearer {token}"},
            )
        except aiohttp.client_exceptions.ClientError:
            raise NotAuthorizedException()

        if resp.status != 200:
            raise NotAuthorizedException()

        try:
            parse_session = eval(unquote(token))
        except Exception:
            raise NotAuthorizedException()

        if "session" not in parse_session:
            raise NotAuthorizedException()

        # Needed to get username.
        result = await connections.get("default").execute_query_dict(
            "SELECT email FROM session_ids WHERE ID = $1",
            [parse_session["session"]],
        )

        if not result:
            raise NotAuthorizedException()

        return AuthenticationResult(user=result[0]["email"], auth=token)


class SaveProgressModel(BaseModel):
    time: float


class ProgressModel(SaveProgressModel):
    video_id: str


class VideoController(Controller):
    path = "/video/{video_ids:str}"

    @get()
    async def progress(
        self, request: Request[str, str, State], video_ids: str
    ) -> list[ProgressModel]:
        results = await VideosTable.filter(
            video_id__in=video_ids.split(","), username=request.user
        ).limit(100)

        progresses = []
        for result in results:
            progresses.append(ProgressModel(time=result.time, video_id=result.video_id))

        return progresses

    @post()
    async def save_progress(
        self, request: Request[str, str, State], data: SaveProgressModel, video_ids: str
    ) -> None:

        if not YOUTUBE_ID_REGEX_COMPLIED.fullmatch(video_ids):
            raise ValidationException()

        await VideosTable.update_or_create(
            video_id=video_ids, username=request.user, defaults={"time": data.time}
        )


async def init_database() -> None:
    await Tortoise.init(
        db_url=URL.create(
            drivername="asyncpg",
            username=SETTINGS.postgre.user,
            password=SETTINGS.postgre.password,
            host=SETTINGS.postgre.host,
            port=SETTINGS.postgre.port,
            database=SETTINGS.postgre.database,
        ).render_as_string(hide_password=False),
        modules={"models": ["syncious.database"]},
    )
    await Tortoise.generate_schemas()


async def close_database() -> None:
    await Tortoise.close_connections()


async def init_aiohttp(app: Litestar) -> None:
    http = getattr(app.state, "http", None)
    if http is None:
        app.state.http = aiohttp.ClientSession(
            # Don't validate SSL if in debug mode.
            connector=aiohttp.TCPConnector(verify_ssl=False) if SETTINGS.debug else None
        )


async def close_aiohttp(app: Litestar) -> None:
    await app.state.http.close()


app = Litestar(
    debug=SETTINGS.debug,
    route_handlers=[VideoController],
    on_startup=[init_database, init_aiohttp],
    on_shutdown=[close_database, close_aiohttp],
    middleware=[DefineMiddleware(BasicAuthMiddleware)],
)
