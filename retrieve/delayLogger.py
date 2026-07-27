import json
import os
import sys
import ssl
import requests
from datetime import datetime, timedelta
import chromadb
from chromadb.utils import embedding_functions

# Vypnutí ověřování pro celý proces
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context

# --- KONFIGURACE ---
GOLEMIO_API_KLIC = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NDY5MSwiaWF0IjoxNzcwMDU2Mzc3LCJleHAiOjExNzcwMDU2Mzc3LCJpc3MiOiJnb2xlbWlvIiwianRpIjoiMGE4YWMwYTMtMjhkYi00MmNiLWJkNDYtYjY4ZjEyZDIwZjUwIn0.RoMCauf3kg3AtHQMeaNOMuqDsnuFpmyXQFGtKPKVoOI"
BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"
DB_PATH = "./chroma_db"

class PIDDelayManager:
    def __init__(self):
        # Kontrola verze Pythonu
        if sys.version_info >= (3, 14):
            print("VAROVÁNÍ: Detekován Python 3.14. ChromaDB nemusí být stabilní. Doporučena verze 3.12/3.13.")
        
        # Inicializace ChromaDB
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # Použití vícejazyčného modelu pro lepší přesnost v češtině (vyžaduje sentence-transformers)
        try:
            self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
        except:
            print("Info: SentenceTransformers není k dispozici, používám výchozí embeddingy.")
            self.ef = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name="prague_mhd_delays",
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"}
        )
        
        self.headers = {
            "X-Access-Token": GOLEMIO_API_KLIC,
            "Content-Type": "application/json"
        }

    def fetch_api_data(self, params):
        """Pomocná metoda pro GET požadavky s ošetřením chyb."""
        try:
            response = requests.get(BASE_URL, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Chyba při komunikaci s Golemio API: {e}")
            return None

    def get_all_routes_for_day(self, date_str):
        """Získá unikátní čísla linek pro daný den."""
        #params = {"date": date_str, "includeArchived": "true", "limit": 2000}
        #data = self.fetch_api_data(params)
        #if not data: return set()
        
        routes = set()
        routes.add(135)  # Přidáno ručně pro testování, protože API nevrací data
        # for feature in data.get('features', []):
            # r_name = feature['properties'].get('gtfs_route_short_name')
            # if r_name and r_name.isdigit():
            #     routes.add(r_name)
        return routes

    def get_route_details(self, route_id, date_str):
        local_route_id = route_id  # Pro případné úpravy ID, pokud by bylo potřeba
        """Získá detaily zpoždění > 10 min pro konkrétní linku."""
        params = {"routeId": route_id, "date": date_str, "delayMin": 10}
        data = self.fetch_api_data(params)
        if not data: return []
        
        results = []
        for f in data.get('features', []):
            p = f['properties']
            results.append({
                "den": datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y"),
                "linka": p.get('gtfs_route_short_name'),
                "zpozdeni_min": round(p.get('delay', 0) / 60),
                "cas": datetime.fromisoformat(p.get('updated_at').replace('Z', '+00:00')).strftime("%H:%M"),
                "zastavka": p.get('last_stop_name', "Neznámá"),
                "smer": p.get('gtfs_trip_headsign', "Neznámý"),
                "pricina": "Dopravní zácpa/nehoda (zjištěno z API)",
                "timestamp_iso": p.get('updated_at')
            })
        return results

    def save_data(self, date_str, transport_type, data_list):
        """Uloží data do JSON a ChromaDB."""
        if not data_list: return
        
        date_clean = date_str.replace("-", "")
        filename = f"{date_clean}_{transport_type}.json"
        
        ids, docs, metas = [], [], []
        
        for item in data_list:
            uid = f"{date_clean}_L{item['linka']}_{item['cas'].replace(':', '')}"
            doc = (f"Mimořádnost {item['den']} v {item['cas']}: Linka {item['linka']} "
                   f"zpoždění {item['zpozdeni_min']} min v zastávce {item['zastavka']} "
                   f"(směr {item['smer']}). Příčina: {item['pricina']}")
            
            meta = {
                "den": item['den'],
                "linka": int(item['linka']),
                "zpozdeni": int(item['zpozdeni_min']),
                "druh": transport_type,
                "typ_incidentu": "zpoždění_nad_10min"
            }
            
            ids.append(uid); docs.append(doc); metas.append(meta)

        self.collection.upsert(ids=ids, documents=docs, metadatas=metas)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        print(f"Uloženo {len(ids)} záznamů pro {transport_type} dne {item['den']}")

# --- SPUŠTĚNÍ ---
if __name__ == "__main__":
    manager = PIDDelayManager()
    DEN_OD = datetime(2026, 2, 12)
    DEN_DO = datetime(2026, 2, 12)
    
    curr = DEN_OD
    while curr <= DEN_DO:
        d_str = curr.strftime("%Y-%m-%d")
        print(f"\n>>> Zpracování dne: {d_str}")
        
        all_routes = manager.get_all_routes_for_day(d_str)
        city, suburb = [], []
        
        # for r in all_routes:
        r = 135  # Pro testování, protože API nevrací data. Odstraňte tento řádek pro reálné použití.
        r_int = int(r)
        details = manager.get_route_details(r, d_str)
        if 100 <= r_int <= 299: city.extend(details)
        elif 300 <= r_int <= 899: suburb.extend(details)
        
        manager.save_data(d_str, "city", city)
        manager.save_data(d_str, "suburb", suburb)
        curr += timedelta(days=1)