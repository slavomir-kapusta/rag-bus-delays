import json
import requests
import os
import ssl
import urllib3

# --- KONFIGURACE SSL (Bypass pro firemní prostředí) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context

# --- API KONFIGURACE ---
GOLEMIO_API_KLIC = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NDY5MSwiaWF0IjoxNzcwMDU2Mzc3LCJleHAiOjExNzcwMDU2Mzc3LCJpc3MiOiJnb2xlbWlvIiwianRpIjoiMGE4YWMwYTMtMjhkYi00MmNiLWJkNDYtYjY4ZjEyZDIwZjUwIn0.RoMCauf3kg3AtHQMeaNOMuqDsnuFpmyXQFGtKPKVoOI"
BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"

routes = set()
routes.add(135)  # Přidáno ručně pro testování, protože API nevrací data

def run_api_query():
    # Parametry dotazu přesně podle tvého zadání
    params = {
        "routeShortName": "135",
        "from": "2026-02-12T00:00:00Z",
        "to": "2026-02-12T23:59:59Z",
        "delayMin": 10
    }
    params = {
        "routeShortName": "135"
    }
    
    headers = {
        "X-Access-Token": GOLEMIO_API_KLIC,
        "Content-Type": "application/json"
    }

    print(f"Spouštím dotaz: GET {BASE_URL}")
    print(f"Parametry: {params}\n")

    try:
        # Provedení dotazu s vypnutým ověřováním SSL
        response = requests.get(
            BASE_URL, 
            headers=headers, 
            params=params, 
            timeout=30, 
            verify=False
        )

        # Kontrola stavového kódu
        if response.status_code != 200:
            print(f"Chyba {response.status_code}: {response.text}")
            return

        data = response.json()
        features = data.get('features', [])

        print(f"Úspěch! Počet nalezených záznamů: {len(features)}")
        print("-" * 60)

        # Výpis výsledků
        for feature in features:
            prop = feature['properties']
            delay_s = prop.get('delay', 0)
            # Pokud je delay None, ošetříme na 0
            delay_min = round(delay_s / 60) if delay_s else 0
            
            print(f"Čas (aktualizace): {prop.get('updated_at')}")
            print(f"Linka: {prop.get('gtfs_route_short_name')} | Zpoždění: {delay_min} min")
            print(f"Poslední zastávka: {prop.get('last_stop_name')} | Směr: {prop.get('gtfs_trip_headsign')}")
            print("-" * 60)

        # Uložení pro debugování
        with open("response_135_archive.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba komunikace: {e}")

if __name__ == "__main__":
    run_api_query()