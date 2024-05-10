# Invidious API Extended
A self-hostable API extension for Invidious, made for custom clients.

## Features
- Watch progress API
  - Keep your watch progress synced between Invidious clients / sessions.
- Integrates with existing Invidious accounts.
- Doesn't rewrite Invidious auth.
- Doesn't modify any existing Invidious records.
- Auth & response caching.
- [API Documentation](https://extended-api.materialio.us/schema).

## Auth
API-Extended uses Invidious SIDs or tokens to validate requests. These should be passed as a Bearer token. If using Invidious tokens, it must have the `GET:feed` scope.

## Supported clients
- [Materialious](https://github.com/WardPearce/Materialious)
    -  Modern material design for Invidious. 

## Deployment
```yaml
services:
  api_extended:
    image: invidious_api_extended:latest
    restart: unless-stopped
    ports:
      - 3004:80
    environment:
      api_extended_postgre: '{"host": "invidious-db", "port": 5432, "database": "invidious", "user": "kemal", "password": "kemal"}'
      api_extended_allowed_origins: '["https://materialios.localhost"]'
      api_extended_debug: false

      # No trailing backslashes!
      api_extended_invidious_instance: "https://invidious.example.com"
      api_extended_production_instance: "https://extended-api.example.com"

      # You can read more about optimizing Syncious here
      # https://hub.docker.com/r/tiangolo/uvicorn-gunicorn
      WEB_CONCURRENCY: 4
```
