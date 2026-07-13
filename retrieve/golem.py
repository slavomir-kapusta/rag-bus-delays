import json
import requests
import os
import ssl
import urllib3
import sys

# --- KONFIGURACE ---
zpozdeni = 1 # min zpoždění v minutách
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context

GOLEMIO_API_KLIC = os.getenv("GOLEMIO_API_KLIC")

if not GOLEMIO_API_KLIC:
    print("CHYBA: Není nastavena proměnná GOLEMIO_API_KEY")
    sys.exit(1)

BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"

def run_api_query():
    # 1. ZMĚNA: Odstranili jsme "routeShortName", aby API vrátilo všechna vozidla
    # Pozor: Stahuje to více dat (cca 1-2 MB JSON)
    params = {
        "limit": 10000  # Pro jistotu zvýšíme limit, abychom pobrali vše
    }
    
    headers = {
        "X-Access-Token": GOLEMIO_API_KLIC,
        "Content-Type": "application/json"
    }

    print("Stahuji data o všech vozidlech...")

    try:
        response = requests.get(BASE_URL, headers=headers, params=params, verify=False)
        
        if response.status_code != 200:
            print(f"Chyba {response.status_code}: {response.text}")
            return

        data = response.json()
        features = data.get('features', [])

        print(f"Staženo {len(features)} vozidel. Filtruji zpoždění > {zpozdeni} min...\n")

        count_delayed = 0

        for feature in features:
            prop = feature['properties']
            
            # Získání zpoždění (v sekundách), převod na minuty
            delay_s = prop.get('delay', 0)
            if delay_s is None: delay_s = 0
            delay_min = round(delay_s / 60)

            # 2. ZMĚNA: Podmínka - vypisujeme jen pokud je zpoždění > 2 minuty
            if delay_min >= zpozdeni:
                count_delayed += 1
                linka = prop.get('gtfs_route_short_name')
                smer = prop.get('gtfs_trip_headsign')
                print(f"Linka {linka} -> {smer}: Zpoždění {delay_min} min")

        print("-" * 40)
        print(f"Celkem nalezeno {count_delayed} spojů se zpožděním větším než {zpozdeni}  minuty.")

    except requests.exceptions.RequestException as e:
        print(f"Chyba komunikace: {e}")

if __name__ == "__main__":
    run_api_query()