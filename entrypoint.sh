#!/bin/bash
set -e

# Write Google credentials from base64 env vars (set in Railway dashboard)
if [ -n "$GOOGLE_CREDENTIALS_B64" ]; then
    echo "$GOOGLE_CREDENTIALS_B64" | base64 -d > /app/google_credentials.json
    echo "[entrypoint] google_credentials.json written"
fi

if [ -n "$GOOGLE_TOKEN_B64" ]; then
    echo "$GOOGLE_TOKEN_B64" | base64 -d > /app/token.json
    echo "[entrypoint] token.json written"
fi

touch /app/memory.md

exec python main.py
