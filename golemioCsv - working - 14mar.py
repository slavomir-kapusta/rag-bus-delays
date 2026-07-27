import json
import requests
import os
import urllib3
import sys
import ssl
import glob
import time
import csv  # Přidán import modulu csv
from datetime import datetime

# --- KONFIGURACE SSL (Bypass pro firemní prostředí) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context

# --- KONFIGURACE SKRIPTU ---
MIN_DELAY = 10 # Minimální zpoždění v minutách pro zápis do JSONu a CSV
SLEEP_TIME = 240 # (   240sec ---= 4 minuty )  
BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"

# Načtení klíče ze systémové proměnné
GOLEMIO_API_KLIC = os.getenv("GOLEMIO_API_KLIC") 

if not GOLEMIO_API_KLIC:
    print("CHYBA: Systémová proměnná 'GOLEMIO_API_KLIC' není nastavena!")
    sys.exit(1)

def get_window_key(dt):
    """Určí správné časové okno podle aktuální hodiny."""
    h = dt.hour
    if 0 <= h < 6: return "zpozdeni_00_06"
    if 6 <= h < 9: return "zpozdeni_06_09"
    if 9 <= h < 12: return "zpozdeni_09_12"
    if 12 <= h < 15: return "zpozdeni_12_15"
    if 15 <= h < 18: return "zpozdeni_15_18"
    return "zpozdeni_18_24"

# --- FUNKCE: Načtení posledních dat (Tabulka + Maximální čas) ---
def load_last_run_data(data_dir="data"):
    """
    Najde poslední dnešní JSON a vrátí:
    1. Nejnovější zaznamenaný arrival_time (max_time).
    2. Slovník záznamů ve formátu {(linka, den, prijezd): zpozdeni}.
    """
    if not os.path.exists(data_dir):
        return None, {}
        
    today_prefix = datetime.now().strftime("%Y%m%d")
    files = sorted(glob.glob(os.path.join(data_dir, f"{today_prefix}_*.json")))
    
    if not files:
        return None, {}
        
    latest_file = files[-1]
    print(f"Čtu poslední soubor pro dnešní den: {latest_file}")
    
    max_time = None
    last_records = {}
    
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                try:
                    meta = item.get("metadata", {})
                    den = meta.get("den")
                    prijezd = meta.get("prijezd")
                    linka = meta.get("linka")
                    zpozdeni = meta.get("zpozdeni", 0)
                    
                    if den and prijezd and linka is not None:
                        # 1. Kontrola a aktualizace maximálního času
                        dt = datetime.strptime(f"{den} {prijezd}", "%d.%m.%Y %H:%M:%S")
                        if max_time is None or dt > max_time:
                            max_time = dt
                            
                        # 2. Vytvoření "tabulky" (slovníku) pro kontrolu duplicit
                        key = (linka, den, prijezd)
                        if key not in last_records or zpozdeni > last_records[key]:
                            last_records[key] = zpozdeni
                            
                except (KeyError, ValueError):
                    continue
    except Exception as e:
        print(f"Varování: Chyba při čtení historického souboru {latest_file}: {e}")
        
    return max_time, last_records
# ---------------------------------------------

def run_api_query(csv_filename):
    # Vytvoření složky data, pokud neexistuje
    if not os.path.exists("data"):
        os.makedirs("data")

    # --- ZÍSKÁNÍ DAT Z POSLEDNÍHO BĚHU ---
    max_old_time, last_records = load_last_run_data("data")
    if max_old_time:
        print(f"Bude se filtrovat podle max času: {max_old_time.strftime('%d.%m.%Y %H:%M:%S')}")
        print(f"Načteno {len(last_records)} záznamů pro kontrolu zpoždění a duplicit.")
    else:
        print("Žádný dnešní předchozí záznam nenalezen. Bude se zpracovávat vše.")

    params = {
        "limit": 10000 # Chceme stáhnout všechna vozidla a filtrovat lokálně
    }
    
    headers = {
        "X-Access-Token": GOLEMIO_API_KLIC,
        "Content-Type": "application/json"
    }

    print(f"Stahuji aktuální data z Golemio API...")

    try:
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=30, verify=False)

        if response.status_code != 200:
            print(f"Chyba API {response.status_code}: {response.text}")
            return

        data = response.json()
        features = data.get('features', [])
        
        output_data = []
        max_current_arrival_time = None
        
        print(f"Zpracovávám {len(features)} vozidel. Hledám zpoždění >= {MIN_DELAY} min...")

        for feature in features:
            prop = feature['properties']
            
            trip_data = prop.get('trip', {})
            gtfs_data = trip_data.get('gtfs', {})
            last_position = prop.get('last_position', {})
            delay_data = last_position.get('delay', {})
            actual_delay = delay_data.get('actual', 0)
            last_stop = last_position.get('last_stop', {})
            arrival_time = last_stop.get('arrival_time', {})

            linka_str = gtfs_data.get('route_short_name', '')
            
            if linka_str.isdigit():
                linka_num = int(linka_str)
                if linka_num < 100 or linka_num > 999:
                    continue
            else:
                continue

            delay_sec = actual_delay
            if delay_sec is None: delay_sec = 0
            delay_min = round(delay_sec / 60)

            if delay_min >= MIN_DELAY:
                linka = linka_num
                zastavka = last_stop.get('id') or "Neznámá zastávka"
                smer = gtfs_data.get('trip_headsign') or "Neznámý směr"
                sekvence = trip_data.get('sequence_id') or " "
                
                lat = feature['geometry']['coordinates'][1]
                lon = feature['geometry']['coordinates'][0]

                try:
                    arrival_time_dt = datetime.fromisoformat(arrival_time)
                    
                    if max_current_arrival_time is None or arrival_time_dt > max_current_arrival_time:
                        max_current_arrival_time = arrival_time_dt
                    
                    arrival_time_naive = arrival_time_dt.replace(tzinfo=None)
                    den_str = arrival_time_dt.strftime('%d.%m.%Y')
                    prijezd_str = arrival_time_dt.strftime('%H:%M:%S')

                    # --- KOMBINOVANÁ FILTRACE ---
                    record_key = (linka, den_str, prijezd_str)
                    
                    if record_key in last_records:
                        old_delay = last_records[record_key]
                        if delay_min <= old_delay:
                            continue
                    else:
                        if max_old_time and arrival_time_naive <= max_old_time:
                            continue 
                    # --------------------------------------------------------

                except ValueError:
                    print("Chyba: Neplatný formát času z API")
                    continue

                if linka==177:
                    print(f"{den_str} {prijezd_str} bus {linka} zpoždění {delay_min} min u zastávky {zastavka} (směr {smer}) ")

                now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                record_id = f"{now_str}_L{linka}"
                
                doc_text = (f"Dne {den_str} měla linka {linka} {sekvence} zpoždění {delay_min} minut "
                            f"u zastávky {zastavka} (směr {smer}) zpožděný příjezd {arrival_time_dt:%H:%M}. "
                            f"Příčina: --- ")

                query_text = f"Vytvoř seznam všech autobusových linek, které měly zpoždění delší než {MIN_DELAY} minut dne {den_str }?"

                windows = {
                    "zpozdeni_00_06": 0, "zpozdeni_06_09": 0, "zpozdeni_09_12": 0,
                    "zpozdeni_12_15": 0, "zpozdeni_15_18": 0, "zpozdeni_18_24": 0
                }
                
                active_window = get_window_key(arrival_time_dt)
                windows[active_window] = delay_min

                item = {
                    "id": record_id,
                    "document": doc_text,
                    "metadata": {
                        "den": den_str,
                        "linka": linka,
                        "zpozdeni": delay_min,
                        "zastavka": zastavka,
                        "lat": lat,
                        "lon": lon,
                        "smer": smer,
                        "kategorie": "provoz",
                        "pricina": "--- ",
                        "prijezd": prijezd_str,
                        "zpozdeni_00_06": windows["zpozdeni_00_06"],
                        "zpozdeni_06_09": windows["zpozdeni_06_09"],
                        "zpozdeni_09_12": windows["zpozdeni_09_12"],
                        "zpozdeni_12_15": windows["zpozdeni_12_15"],
                        "zpozdeni_15_18": windows["zpozdeni_15_18"],
                        "zpozdeni_18_24": windows["zpozdeni_18_24"],
                        "query": query_text,
                        "timestamp": now_str
                    }
                }
                
                output_data.append(item)

        # Uložení do souboru JSON a CSV
        if output_data:
            file_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                
            json_filename = "data/" + file_time_str + ".json"
            
            # 1. Zápis do JSONu
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
                
            # 2. Inkrementální zápis do CSV
            with open(csv_filename, mode="a", newline="", encoding="utf-8-sig") as csv_f:
                writer = csv.writer(csv_f, delimiter=";")
                for item in output_data:
                    meta = item["metadata"]
                    writer.writerow([
                        item["id"],
                        meta["timestamp"],
                        meta["den"],
                        meta["prijezd"],
                        meta["linka"],
                        meta["zpozdeni"],
                        meta["zastavka"],
                        meta["smer"],
                        meta["lat"],
                        meta["lon"]
                    ])
                
            print("-" * 60)
            print(f"ÚSPĚCH: Nalezeno a zapsáno {len(output_data)} NOVÝCH/AKTUALIZOVANÝCH zpoždění autobusů.")
            print(f"Data uložena do: {json_filename} a připsána do {csv_filename}")
        else:
            print("-" * 60)
            print("INFO: Nebyla nalezena žádná nová zpoždění od posledního záznamu. Zápis se neprovádí.")

    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba komunikace s API: {e}")
    except Exception as e:
        print(f"Neočekávaná chyba: {e}")

if __name__ == "__main__":
    # Pojištění existence složky
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Vytvoření hlavního CSV pro tento běh programu
    session_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_csv_filename = os.path.join("data", f"export_zpozdeni_{session_start_time}.csv")
    
    print(f"Inicializuji hlavní CSV soubor: {master_csv_filename}")
    with open(master_csv_filename, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        # Definice hlavičky pro Excel
        writer.writerow(["ID Záznamu", "Timestamp", "Den", "Čas příjezdu", "Linka", "Zpoždění (min)", "Zastávka", "Směr", "Zeměpisná šířka (Lat)", "Zeměpisná délka (Lon)"])

    print("Spouštím nekonečnou smyčku dotazování. Pro ukončení stiskněte Ctrl+C.")
    try:
        while True:
            print(f"\n--- Spouštím dotaz v {datetime.now().strftime('%H:%M:%S')} ---")
            run_api_query(master_csv_filename) # Předáváme název souboru
            print("Čekám " + str(SLEEP_TIME / 60) + " minuty na další dotaz...\n")
            time.sleep(SLEEP_TIME)  
    except KeyboardInterrupt:
        print("\nSkript byl ručně ukončen uživatelem.")
        sys.exit(0)