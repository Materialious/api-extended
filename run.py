import uvicorn

from syncious import app


def main() -> None:
    uvicorn.run(app)
