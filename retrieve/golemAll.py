import json
import requests
import os
import urllib3
import sys
import ssl

# --- KONFIGURACE SSL (Bypass pro firemní prostředí) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context


# --- KONFIGURACE ---
zpozdeni = 2 # min zpoždění v minutách
routes = set()

# Původní ruční přidání (pokud chcete i 135, odkomentujte a dejte do uvozovek)
# routes.add("135") 

# 3. Hromadné přidání všech dotčených linek
seznam_linek = [
    "315", "342", "560", "381", "481", "533", "705", "782", "783", "786", 
    "788", "801", "805", "315", "345", "427", "700", "714", "715", "720", 
    "721", "722", "730", "734", "736", "737", "738", "739", "763", "775", 
    "487", "675", "679", "681", "702", "705", "706", "785", "821", "822", 
    "824", "390", "438", "485", "X390", "305", "573", "316", "954"
]

routes.update(seznam_linek)

print(f"Sleduji celkem {len(routes)} unikátních linek.")

# --- API KONFIGURACE ---
BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"
# POZOR: Ujistěte se, že proměnná prostředí se jmenuje stejně (KEY vs KLIC)
GOLEMIO_API_KLIC = os.getenv("GOLEMIO_API_KLIC")   

# Kontrola, zda byl klíč načten
if not GOLEMIO_API_KLIC:
    print("CHYBA: Systémová proměnná 'GOLEMIO_API_KLIC' není nastavena!")
    print("Prosím nastavte ji před spuštěním skriptu (set GOLEMIO_API_KLIC=...).")
    sys.exit(1)
    

def run_api_query():
    # ZMĚNA: Stahujeme všechna data, filtrovat budeme až v Pythonu.
    # Je to spolehlivější než posílat 50 čísel linek v URL.
    params = {
        "limit": 10000
    }
    
    headers = {
        "X-Access-Token": GOLEMIO_API_KLIC,
        "Content-Type": "application/json"
    }

    print(f"Spouštím dotaz: GET {BASE_URL}")
    print(f"Stahuji data o všech vozidlech a filtruji váš seznam...\n")

    try:
        response = requests.get(
            BASE_URL, 
            headers=headers, 
            params=params, 
            timeout=30, 
            verify=False
        )

        if response.status_code != 200:
            print(f"Chyba {response.status_code}: {response.text}")
            return

        data = response.json()
        features = data.get('features', [])
        
        filtered_features = [] # Sem si uložíme jen nalezené pro export
        count_found = 0

        # Výpis výsledků
        for feature in features:
            prop = feature['properties']
            linka = prop.get('gtfs_route_short_name')

            # --- HLAVNÍ ZMĚNA: FILTROVÁNÍ ---
            # Pokud linka NENÍ v našem seznamu routes, přeskočíme ji
            if linka not in routes:
                continue

            # Pokud jsme tady, linka je v seznamu. Počítáme zpoždění.
            delay_s = prop.get('delay', 0)
            delay_min = round(delay_s / 60) if delay_s else 0

            # Kontrola limitu zpoždění
            if delay_min >= zpozdeni:
                count_found += 1
                filtered_features.append(feature) # Uložíme do seznamu pro JSON
                
                print(f"Linka: {linka} | Zpoždění: {delay_min} min")
                print(f"Směr: {prop.get('gtfs_trip_headsign')} | Zastávka: {prop.get('last_stop_name')}")
                print(f"Aktualizace: {prop.get('updated_at')}")
                print("-" * 60)

        print(f"Hotovo. Nalezeno {count_found} spojů z vašeho seznamu se zpožděním >= {zpozdeni} min.")

        # Uložení jen vyfiltrovaných dat
        output_data = {"features": filtered_features}
        with open("response_filtered_archive.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba komunikace: {e}")

if __name__ == "__main__":
    run_api_query()