import os
import glob
import json
import asyncio
from datetime import datetime, timedelta
from pyzeebe import ZeebeWorker, create_insecure_channel

OVERLAP_TIME = 120

def load_last_run_data(data_dir="data"):
    if not os.path.exists(data_dir):
        return None, {}
    today_prefix = datetime.now().strftime("%Y%m%d")
    files = sorted(glob.glob(os.path.join(data_dir, f"{today_prefix}_*.json")))
    if not files:
        return None, {}
    
    latest_file = files[-1]
    last_records = {}
    max_time = None

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                meta = item.get("metadata", {})
                den, prijezd, linka = meta.get("den"), meta.get("prijezd"), meta.get("linka")
                obeh, vozidlo, zpozdeni = meta.get("obeh"), meta.get("vozidlo"), meta.get("zpozdeni", 0)
                
                if den and prijezd and linka is not None:
                    dt = datetime.strptime(f"{den} {prijezd}", "%d.%m.%Y %H:%M:%S")
                    if max_time is None or dt > max_time:
                        max_time = dt
                    
                    key = f"{linka}_{obeh}_{vozidlo}_{den}_{prijezd}"
                    if key not in last_records or zpozdeni > last_records[key]:
                        last_records[key] = zpozdeni
    except Exception as e:
        print(f"Warning reading history: {e}")

    max_old_str = (max_time - timedelta(seconds=OVERLAP_TIME)).strftime("%d.%m.%Y %H:%M:%S") if max_time else None
    return max_old_str, last_records

async def main():
    channel = create_insecure_channel(hostname="localhost", port=26500)
    worker = ZeebeWorker(channel)

    @worker.task(task_type="load-history")
    def handle_load_history():
        print("\n[Worker: load-history] Loading historical run data...")
        max_old_str, last_records = load_last_run_data()
        
        return {
            "maxOldTime": max_old_str,
            "lastRecords": last_records
        }

    print("Worker [load-history] listening on port 26500...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())