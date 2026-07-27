import typing
import typing_extensions
import json
import os
import requests
from datetime import datetime, timedelta
import chromadb
from chromadb.utils import embedding_functions

# Oprava pro Pydantic v1 v nových verzích Pythonu
if not hasattr(typing, 'Annotated'):
    typing.Annotated = typing_extensions.Annotated

# Konstanty pro API
GOLEMIO_API_KLIC = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NDY5MSwiaWF0IjoxNzcwMDU2Mzc3LCJleHAiOjExNzcwMDU2Mzc3LCJpc3MiOiJnb2xlbWlvIiwianRpIjoiMGE4YWMwYTMtMjhkYi00MmNiLWJkNDYtYjY4ZjEyZDIwZjUwIn0.RoMCauf3kg3AtHQMeaNOMuqDsnuFpmyXQFGtKPKVoOI"
BASE_URL = "https://api.golemio.cz/v2/vehiclepositions"

class PIDDelayManager:
    def __init__(self, db_path="./chroma_db"):
        # Inicializace ChromaDB
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="prague_mhd_delays",
            metadata={"hnsw:space": "cosine"}
        )
        self.headers = {
            "X-Access-Token": GOLEMIO_API_KLIC,
            "Content-Type": "application/json"
        }

    def fetch_routes_with_delays(self, date_str):
        """Získá seznam unikátních linek, které měly v daný den zpoždění."""
        params = {
            "date": date_str,
            "includeArchived": "true",
            "limit": 1000 # Nastavení limitu pro hromadný sběr
        }
        response = requests.get(BASE_URL, headers=self.headers, params=params)
        if response.status_code != 200:
            print(f"Chyba API (hromadný dotaz): {response.status_code}")
            return set()
        
        data = response.json()
        # Vyfiltrování unikátních čísel linek (100-299 městské, 300-899 příměstské)
        routes = set()
        for feature in data.get('features', []):
            route_name = feature['properties'].get('gtfs_route_short_name')
            if route_name and route_name.isdigit():
                routes.add(route_name)
        return routes

    def fetch_delay_details(self, route_id, date_str):
        """Získá konkrétní detaily zpoždění nad 10 minut pro danou linku."""
        params = {
            "routeId": route_id,
            "date": date_str,
            "delayMin": 10
        }
        response = requests.get(BASE_URL, headers=self.headers, params=params)
        if response.status_code != 200:
            return []
        
        details = []
        data = response.json()
        for feature in data.get('features', []):
            prop = feature['properties']
            geom = feature.get('geometry', {}).get('coordinates', [0, 0])
            
            details.append({
                "den": datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y"),
                "linka": prop.get('gtfs_route_short_name'),
                "zpozdeni_min": round(prop.get('delay', 0) / 60),
                "cas": datetime.fromisoformat(prop.get('updated_at').replace('Z', '+00:00')).strftime("%H:%M"),
                "zastavka": prop.get('last_stop_name', "Neznámá"),
                "smer": prop.get('gtfs_trip_headsign', "Neznámý"),
                "pricina": "Dopravní komplikace (automatický záznam API)",
                "kategorie": "zácpa", # Výchozí kategorie pro RAG
                "gps": f"{geom[1]}, {geom[0]}",
                "timestamp_iso": prop.get('updated_at')
            })
        return details

    def process_delays(self, date_str, transport_type, data_list, original_query):
        """Uloží data do JSON a ChromaDB."""
        if not data_list:
            return

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_clean = date_str.replace("-", "")
        type_suffix = "city" if transport_type == "městská" else "suburb"
        filename = f"{date_clean}{type_suffix}_{timestamp_str}.json"
        
        json_output = []
        for item in data_list:
            doc_id = f"{date_clean}_L{item['linka']}_{item['cas'].replace(':', '')}"
            document_text = (f"Dne {item['den']} měla {transport_type} linka {item['linka']} "
                             f"zpoždění {item['zpozdeni_min']} min v {item['cas']} u zastávky "
                             f"{item['zastavka']} (směr {item['smer']}). Příčina: {item['pricina']}.")
            
            metadata = {
                "den": item['den'],
                "timestamp": item['timestamp_iso'],
                "linka": int(item['linka']),
                "zpozdeni_min": int(item['zpozdeni_min']),
                "kategorie": item['kategorie'],
                "druh": transport_type,
                "gps": item['gps'],
                "query": original_query[:200]
            }
            
            json_output.append({"id": doc_id, "document": document_text, "metadata": metadata})
            
            self.collection.add(
                documents=[document_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, ensure_ascii=False, indent=2)
        print(f"Uloženo: {filename} ({len(json_output)} záznamů)")

# --- HLAVNÍ CYKLUS ---
if __name__ == "__main__":
    manager = PIDDelayManager()
    
    # Definice cyklu dní
    DEN_OD = datetime(2026, 2, 1)
    DEN_DO = datetime(2026, 2, 2)
    
    current_date = DEN_OD
    while current_date <= DEN_DO:
        formatted_date = current_date.strftime("%Y-%m-%d")
        print(f"\n--- Zpracovávám den: {formatted_date} ---")
        
        # 1. Získání seznamu linek
        all_routes = manager.fetch_routes_with_delays(formatted_date)
        
        city_delays = []
        suburb_delays = []
        
        # 2. Iterace přes linky a získání detailů
        for route in all_routes:
            route_num = int(route)
            details = manager.fetch_delay_details(route, formatted_date)
            
            if 100 <= route_num <= 299:
                city_delays.extend(details)
            elif 300 <= route_num <= 899:
                suburb_delays.extend(details)
        
        # 3. Zpracování a uložení
        query_text = f"Zpoždění linek pro den {formatted_date}"
        manager.process_delays(formatted_date, "městská", city_delays, query_text)
        manager.process_delays(formatted_date, "příměstská", suburb_delays, query_text)
        
        current_date += timedelta(days=1)