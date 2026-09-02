#!/bin/bash
set -e

# Start Brain Worker in the background
python3 -u brain_worker.py &

# Start Muscle Worker in the foreground (keeps container alive)
exec python3 -u muscle_worker.py
