from litestar import Controller, Litestar, get, post
from litestar.exceptions import NotFoundException
from pydantic import BaseModel
from sqlalchemy.engine.url import URL
from tortoise import Tortoise

from syncious.database import VideosTable
from syncious.env import SETTINGS


class ProgressModel(BaseModel):
    time: float


class VideoController(Controller):
    path = "/video/{video_id:str}"

    @get()
    async def progress(self, video_id: str) -> ProgressModel:
        result = await VideosTable.get(video_id=video_id, email="wardpearce@pm.me")

        if not result:
            raise NotFoundException()

        return ProgressModel(time=result.time)

    @post()
    async def save_progress(self, data: ProgressModel, video_id: str) -> None:
        await VideosTable.update_or_create(
            video_id=video_id, email="wardpearce@pm.me", defaults={"time": data.time}
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


app = Litestar(
    route_handlers=[VideoController],
    on_startup=[init_database],
    on_shutdown=[close_database],
    debug=True,
)
