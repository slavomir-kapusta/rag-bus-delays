import os
import csv
import json
import asyncio
from datetime import datetime
from pyzeebe import ZeebeWorker, create_insecure_channel

async def main():
    channel = create_insecure_channel(hostname="localhost", port=26500)
    worker = ZeebeWorker(channel)

    @worker.task(task_type="export-data")
    def handle_export(filteredVehicles: list):
        print("\n[Worker: export-data] Exporting records to file...")
        if not os.path.exists("data"):
            os.makedirs("data")

        file_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"data/{file_time_str}.json"
        csv_filename = f"data/export_zpozdeni_{file_time_str}.csv"

        # 1. Export JSON
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(filteredVehicles, f, ensure_ascii=False, indent=2)

        # 2. Export CSV
        with open(csv_filename, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["ID Záznamu", "Timestamp", "Den", "Čas příjezdu", "Linka", "Oběh", "Vozidlo", "Zpoždění (min)", "Zastávka", "Směr", "Lat", "Lon"])
            for item in filteredVehicles:
                meta = item["metadata"]
                writer.writerow([
                    item["id"], meta["timestamp"], meta["den"], meta["prijezd"],
                    meta["linka"], meta["obeh"], meta["vozidlo"], meta["zpozdeni"],
                    meta["zastavka"], meta["smer"], meta["lat"], meta["lon"]
                ])

        print(f"Exported {len(filteredVehicles)} items to {json_filename} and {csv_filename}")
        return {"exportStatus": "SUCCESS"}

    print("Worker [export-data] listening on port 26500...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())