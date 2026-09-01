import time
import subprocess
print("Started Muscle Worker loop in background...")
while True:
    subprocess.run(["/Users/ramakrishnachanda/Desktop/greenhosue/venv/bin/python3", "muscle_worker.py"])
    time.sleep(10)
