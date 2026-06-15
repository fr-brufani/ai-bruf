#!/bin/bash
# Avvia il bot in locale per sviluppo
# Ferma prima la macchina Fly per evitare conflitti Telegram

export PATH="$HOME/.fly/bin:$PATH"

echo "⏸  Fermo il bot su Fly.io..."
fly machine stop d8d9245c4d5968 -a ai-bruf-bot 2>/dev/null && echo "✓ Fly fermato" || echo "⚠ Fly già fermo o errore"

echo "🚀 Avvio bot in locale..."
pkill -f "main.py" 2>/dev/null
cd "$(dirname "$0")"
python main.py
