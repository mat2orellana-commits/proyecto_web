#!/usr/bin/env bash
# Arranca el backend de Sakura Player (FastAPI + ytmusicapi)
cd "$(dirname "$0")"
exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
