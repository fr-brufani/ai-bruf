#!/bin/bash
# Deploy su Fly.io a fine sessione

export PATH="$HOME/.fly/bin:$PATH"

echo "⏹  Fermo il bot locale..."
pkill -f "main.py" 2>/dev/null && echo "✓ Locale fermato" || echo "⚠ Nessun processo locale"

echo "🚀 Deploy su Fly.io..."
cd "$(dirname "$0")"
fly deploy --ha=false

echo "✅ Deploy completato — bot live su Fly.io"
