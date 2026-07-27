# run_all_workers.py
import subprocess
import sys

scripts = [
    "workers/worker_load_history.py",
    "workers/worker_fetch_golemio.py",
    "workers/worker_filter.py",
    "workers/worker_export.py"
]

processes = []
for script in scripts:
    # Starts all worker scripts in the background
    p = subprocess.Popen([sys.executable, script])
    processes.append(p)

print("All Camunda workers are running. Press Ctrl+C to stop.")

try:
    for p in processes:
        p.wait()
except KeyboardInterrupt:
    for p in processes:
        p.terminate()
    print("\nWorkers stopped.")