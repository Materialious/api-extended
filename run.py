import uvicorn

from syncious.main import app


def main() -> None:
    uvicorn.run(app)
