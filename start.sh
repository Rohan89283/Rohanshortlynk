#!/bin/sh
set -e
uvicorn worker.app:app --host 0.0.0.0 --port 8000 &
exec python main.py
