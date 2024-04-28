from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgreSettings(BaseModel):
    database: str = "invidious"
    user: str = "kemal"
    password: str = "kemal"
    host: str
    port: int = 5432


class Settings(BaseSettings):
    model_config: SettingsConfigDict = {"env_prefix": "syncious_"}

    debug: bool = False

    invidious_instance: str
    production_instance: str

    allowed_origins: list[str]

    postgre: PostgreSettings


SETTINGS = Settings()  # type: ignore
