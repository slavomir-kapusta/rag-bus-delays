import os
import requests
import urllib3
import asyncio
from pyzeebe import ZeebeWorker, create_insecure_channel

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"
GOLEMIO_API_KLIC = os.getenv("GOLEMIO_API_KLIC", "YOUR_API_KEY_HERE")

async def main():
    channel = create_insecure_channel(hostname="localhost", port=26500)
    worker = ZeebeWorker(channel)

    @worker.task(task_type="fetch-golemio-data")
    def handle_fetch():
        print("\n[Worker: fetch-golemio-data] Querying Golemio API...")
        headers = {
            "X-Access-Token": GOLEMIO_API_KLIC,
            "Content-Type": "application/json"
        }
        params = {"limit": 10000}

        try:
            response = requests.get(BASE_URL, headers=headers, params=params, timeout=30, verify=False)
            if response.status_code == 200:
                features = response.json().get('features', [])
                print(f"Fetched {len(features)} vehicle records.")
                return {"rawVehicles": features}
            else:
                print(f"API Error {response.status_code}: {response.text}")
                return {"rawVehicles": []}
        except Exception as e:
            print(f"API Connection Exception: {e}")
            return {"rawVehicles": []}

    print("Worker [fetch-golemio-data] listening on port 26500...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())