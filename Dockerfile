FROM tiangolo/uvicorn-gunicorn:python3.11
LABEL maintainer="Ward Pearce <wardpearce@pm.me>"

COPY ./syncious /

RUN pip3 install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev

COPY ./syncious /app

EXPOSE 8000