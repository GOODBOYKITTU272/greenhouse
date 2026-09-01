#!/bin/zsh
# Load the user's local environment variables where OPENAI_API_KEY is stored
source ~/.zshrc
source ~/.zprofile 2>/dev/null
export PATH="/Users/ramakrishnachanda/Desktop/greenhosue/venv/bin:$PATH"
nohup python3 /Users/ramakrishnachanda/Desktop/greenhosue/brain_worker.py > /Users/ramakrishnachanda/Desktop/greenhosue/brain.log 2>&1 &
