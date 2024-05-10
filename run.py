import uvicorn

from api_extended.main import app


def main() -> None:
    uvicorn.run(app)
