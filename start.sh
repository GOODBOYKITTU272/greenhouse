#!/bin/bash
set -e

echo "🚀 Starting ApplyWizz Container Services..."
echo "🧠 Launching Brain Worker (background)..."
python3 -u brain_worker.py &

echo "🦾 Launching Muscle Worker (foreground)..."
exec python3 -u muscle_worker.py
