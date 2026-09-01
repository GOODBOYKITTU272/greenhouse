#!/bin/bash
# Start Brain Worker in the background
python3 brain_worker.py &
# Start Muscle Worker in the foreground (keeps container alive)
python3 muscle_worker.py
