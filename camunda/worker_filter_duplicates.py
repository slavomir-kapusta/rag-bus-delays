import asyncio
from datetime import datetime
from pyzeebe import ZeebeWorker, create_insecure_channel

MIN_DELAY = 10

def get_window_key(dt):
    h = dt.hour
    if 0 <= h < 6: return "zpozdeni_00_06"
    if 6 <= h < 9: return "zpozdeni_06_09"
    if 9 <= h < 12: return "zpozdeni_09_12"
    if 12 <= h < 15: return "zpozdeni_12_15"
    if 15 <= h < 18: return "zpozdeni_15_18"
    return "zpozdeni_18_24"

async def main():
    channel = create_insecure_channel(hostname="localhost", port=26500)
    worker = ZeebeWorker(channel)

    @worker.task(task_type="filter-duplicates")
    def handle_filter(rawVehicles: list, lastRecords: dict = None):
        print("\n[Worker: filter-duplicates] Filtering vehicle delays...")
        last_records = lastRecords or {}
        output_data = []

        for feature in rawVehicles:
            prop = feature.get('properties', {})
            trip_data = prop.get('trip', {})
            gtfs_data = trip_data.get('gtfs', {})
            last_position = prop.get('last_position', {})
            delay_data = last_position.get('delay', {})
            actual_delay = delay_data.get('actual', 0) or 0
            last_stop = last_position.get('last_stop', {})
            arrival_time = last_stop.get('arrival_time')

            linka_str = gtfs_data.get('route_short_name', '')
            if not linka_str.isdigit():
                continue
            
            linka_num = int(linka_str)
            if linka_num < 100 or linka_num > 999:
                continue

            delay_min = round(actual_delay / 60)
            if delay_min >= MIN_DELAY and arrival_time:
                try:
                    arrival_time_dt = datetime.fromisoformat(arrival_time)
                    den_str = arrival_time_dt.strftime('%d.%m.%Y')
                    prijezd_str = arrival_time_dt.strftime('%H:%M:%S')
                    sequence = trip_data.get('sequence_id', '')
                    vehicle = trip_data.get('vehicle_registration_number', '')

                    record_key = f"{linka_num}_{sequence}_{vehicle}_{den_str}_{prijezd_str}"

                    if record_key in last_records and delay_min <= last_records[record_key]:
                        continue

                    zastavka = last_stop.get('id') or "Neznámá zastávka"
                    smer = gtfs_data.get('trip_headsign') or "Neznámý směr"
                    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")

                    output_data.append({
                        "id": f"{now_str}_L{linka_num}",
                        "metadata": {
                            "timestamp": now_str,
                            "den": den_str,
                            "prijezd": prijezd_str,
                            "linka": linka_num,
                            "obeh": sequence,
                            "vozidlo": vehicle,
                            "zpozdeni": delay_min,
                            "zastavka": zastavka,
                            "smer": smer,
                            "lat": feature['geometry']['coordinates'][1],
                            "lon": feature['geometry']['coordinates'][0]
                        }
                    })
                except ValueError:
                    continue

        has_new_delays = len(output_data) > 0
        print(f"Filter finished. New delays found: {len(output_data)} -> hasNewDelays = {has_new_delays}")

        # Setting hasNewDelays variable dictates Gateway branch logic natively in Camunda
        return {
            "filteredVehicles": output_data,
            "hasNewDelays": has_new_delays
        }

    print("Worker [filter-duplicates] listening on port 26500...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())
    