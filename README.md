# Syncious
Sync your watch progress between Invidious sessions.

## Features
- Integrates with existing Invidious accounts.
- Automatically deletes any watch history for users who delete their Invidious account (within an hour.)
- Doesn't rewrite Invidious auth.
- Doesn't modify any existing Invidious records.
- Auth caching.
- [API Documentation](syncious.materialio.us/schema)

## Supported clients
- [Materialious](https://github.com/WardPearce/Materialious)
    -  Modern material design for Invidious. 

## Deployment
```yaml
services:
  syncious:
    image: wardpearce/syncious:latest
    restart: unless-stopped
    ports:
      - 3004:80
    environment:
      syncious_postgre: '{"host": "invidious-db", "port": 5432, "database": "invidious", "user": "kemal", "password": "kemal"}'
      syncious_allowed_origins: '["https://materialios.localhost"]'
      syncious_debug: false

      # No trailing backslashes!
      syncious_invidious_instance: "https://invidious.example.com"
      syncious_production_instance: "https://syncious.example.com"
```
