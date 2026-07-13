import json
import requests
import os
import urllib3
import sys  # Ukončení skriptu při chybě
import ssl

# --- KONFIGURACE SSL (Bypass pro firemní prostředí) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context


# --- KONFIGURACE ---
zpozdeni = 2 # min zpoždění v minutách
routes = set()
#routes.add(135)  # Přidáno ručně pro testování, protože API nevrací data
#Dotčené linky: Zpoždění a omezení jsou evidována u linek 315, 342, 560, 381, 481, 533, 705, 782, 783, 786, 788, 801, 805, 315, 345, 427, 700, 714, 715, 720, 721, 722, 730, 734, 736, 737, 738, 739, 763, 775, 487, 675, 679, 681, 702, 705, 706, 785, 821, 822, 824, 390, 438, 485, X390, 305, 573, 316, 954.

# 3. Hromadné přidání všech dotčených linek
# Používáme stringy ("..."), aby to fungovalo i pro X390
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
GOLEMIO_API_KLIC = os.getenv("GOLEMIO_API_KLIC")   # Načtení klíče ze systémové proměnné

# Kontrola, zda byl klíč načten
if not GOLEMIO_API_KLIC:
    print("CHYBA: Systémová proměnná 'GOLEMIO_API_KLIC' není nastavena!")
    print("Prosím nastavte ji před spuštěním skriptu.")
    sys.exit(1)
    

def run_api_query():
    # Parametry dotazu přesně podle tvého zadání
    #params = { "routeShortName": "135", nefunguje: "from": "2026-02-12T00:00:00Z", "to": "2026-02-12T23:59:59Z","delayMin": 10
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

            if delay_min >= zpozdeni:
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