import importlib.metadata
import json
import re
from datetime import timezone
from typing import cast
from urllib.parse import unquote

import aiohttp
import aiohttp.client_exceptions
from aiocron import crontab
from litestar import Controller, Litestar, Request, delete, get, post
from litestar.config.cors import CORSConfig
from litestar.connection import ASGIConnection
from litestar.datastructures import State
from litestar.exceptions import NotAuthorizedException, ValidationException
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
from litestar.middleware.base import DefineMiddleware
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.openapi.spec import (
    Components,
    ExternalDocumentation,
    SecurityScheme,
    Server,
)
from pydantic import BaseModel
from sqlalchemy.engine.url import URL
from tortoise import Tortoise, connections

from syncious.database import VideosTable
from syncious.env import SETTINGS

YOUTUBE_ID_REGEX_COMPLIED = re.compile(r"[a-zA-Z0-9_-]{11}")


class BasicAuthMiddleware(AbstractAuthenticationMiddleware):
    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        authorization = connection.headers.get("Authorization")

        if not authorization or not authorization.startswith(("Bearer ", "bearer ")):
            raise NotAuthorizedException()

        token = authorization.removeprefix("Bearer ").removeprefix("bearer ")

        cache = connection.app.stores.get("auth_cache")

        cached_email = await cache.get(token)
        if cached_email is not None:
            return AuthenticationResult(user=cached_email.decode(), auth=token)

        http = cast(aiohttp.ClientSession, connection.app.state.http)

        cooke_token = False
        try:
            parse_session = json.loads(unquote(token))
        except json.JSONDecodeError:
            cooke_token = True

        # Lets not rewrite how Invidious validates tokens
        try:
            resp = await http.get(
                f"{SETTINGS.invidious_instance}/api/v1/auth/feed",
                headers=(
                    {"Authorization": f"Bearer {token}"} if not cooke_token else None
                ),
                cookies={"SID": token} if cooke_token else None,
            )
        except aiohttp.client_exceptions.ClientError:
            raise NotAuthorizedException()

        if resp.status != 200:
            raise NotAuthorizedException()

        session_id = ""
        if not cooke_token:
            if "session" not in parse_session:
                raise NotAuthorizedException()

            session_id = parse_session["session"]
        else:
            session_id = token

        if not session_id:
            raise NotAuthorizedException()

        # Needed to get username.
        result = await connections.get("default").execute_query_dict(
            "SELECT email FROM session_ids WHERE ID = $1",
            [session_id],
        )

        if not result:
            raise NotAuthorizedException()

        await cache.set(token, result[0]["email"], 60)

        return AuthenticationResult(user=result[0]["email"], auth=token)


class SaveProgressModel(BaseModel):
    time: float


class ProgressModel(SaveProgressModel):
    video_id: str


class VideoController(Controller):
    path = "/video/{video_id:str}"

    @get(
        description="You can pass video IDs comma separated up to 100 IDs to get multiple video progresses."
    )
    async def progress(
        self, request: Request[str, str, State], video_id: str
    ) -> list[ProgressModel]:
        results = await VideosTable.filter(
            video_id__in=video_id.split(","), username=request.user
        ).limit(100)

        progresses = []
        for result in results:
            progresses.append(ProgressModel(time=result.time, video_id=result.video_id))

        return progresses

    @delete()
    async def delete_progress(
        self, request: Request[str, str, State], video_id: str
    ) -> None:
        if not YOUTUBE_ID_REGEX_COMPLIED.fullmatch(video_id):
            raise ValidationException()

        await VideosTable.filter(video_id=video_id, username=request.user).delete()

    @post()
    async def save_progress(
        self, request: Request[str, str, State], data: SaveProgressModel, video_id: str
    ) -> None:

        if not YOUTUBE_ID_REGEX_COMPLIED.fullmatch(video_id):
            raise ValidationException()

        await VideosTable.update_or_create(
            video_id=video_id, username=request.user, defaults={"time": data.time}
        )


@delete("/videos", description="Deletes all watch progress for a user.")
async def delete_all_watch(request: Request[str, str, State]) -> None:
    await VideosTable.filter(username=request.user).delete()


async def crontab_check_for_deleted() -> None:
    """Background task to check if a user has deleted their Invidious account."""

    results = await connections.get("default").execute_query_dict(
        "SELECT email FROM users"
    )

    invidious_usernames: list[str] = [result["email"] for result in results]

    syncious_usernames = (
        await VideosTable.filter().distinct().values_list("username", flat=True)
    )

    to_delete = []

    for syncious_username in syncious_usernames:
        if syncious_username in invidious_usernames:
            continue

        to_delete.append(syncious_username)

    if to_delete:
        await VideosTable.filter(username__in=to_delete).delete()


async def start_crontab(app: Litestar) -> None:
    crontab_state = getattr(app.state, "crontab", None)
    if crontab_state is None:
        app.state.crontab = crontab(
            "0 */1 * * *", start=False, tz=timezone.utc, func=crontab_check_for_deleted
        )

        app.state.crontab.start()


async def stop_crontab(app: Litestar) -> None:
    app.state.crontab.stop()


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


class ScalarRenderPluginRouteFix(ScalarRenderPlugin):
    @staticmethod
    def get_openapi_json_route(request: Request) -> str:
        return f"{SETTINGS.production_instance}/schema/openapi.json"


app = Litestar(
    debug=SETTINGS.debug,
    route_handlers=[VideoController, delete_all_watch],
    cors_config=CORSConfig(
        allow_origins=SETTINGS.allowed_origins,
        allow_methods=["OPTIONS", "GET", "DELETE", "POST"],
    ),
    openapi_config=OpenAPIConfig(
        title="Syncious",
        version=importlib.metadata.version("syncious"),
        description="Sync your watch progress between Invidious sessions.",
        external_docs=ExternalDocumentation(
            url="https://docs.invidious.io/api/authenticated-endpoints/",
            description="How to generate authorization tokens for Invidious.",
        ),
        security=[{"BearerToken": []}],
        render_plugins=[ScalarRenderPluginRouteFix()],
        servers=[
            Server(SETTINGS.production_instance, "Production API path for Syncious.")
        ],
        components=Components(
            security_schemes={
                "BearerToken": SecurityScheme(
                    type="http",
                    scheme="bearer",
                )
            },
        ),
    ),
    on_startup=[init_database, init_aiohttp, start_crontab],
    on_shutdown=[close_database, close_aiohttp, stop_crontab],
    middleware=[DefineMiddleware(BasicAuthMiddleware, exclude=["/schema"])],
)
