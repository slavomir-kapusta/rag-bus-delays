import json
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
import os
import re
import glob
import shutil  # <--- NOVÝ IMPORT pro manipulaci se soubory
from datetime import datetime

# --- KONFIGURACE ---
DATA_DIR = r"C:\AI\aJizdniVykony\delay\data"
PROCESSED_DIR = r"C:\AI\aJizdniVykony\delay\data\processed"  # <--- NOVÁ SLOŽKA PRO ARCHIV
DB_PATH = r"C:\AI\aJizdniVykony\delay\chroma_db"
COLLECTION_NAME = "delays"
MODEL_PATH = r"C:\AI\models\paraphrase-multilingual-MiniLM-L12-v2"

# --- 1. DEFINICE TŘÍDY PRO EMBEDDING ---
class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path):
        print(f"   -> Inicializuji SentenceTransformer z: {model_path}")
        try:
            self.model = SentenceTransformer(model_path)
        except Exception as e:
            print(f"\n!!! KRITICKÁ CHYBA PŘI NAČÍTÁNÍ MODELU !!!\nChyba: {e}")
            raise e

    def __call__(self, input: Documents) -> Embeddings:
        return self.model.encode(input, convert_to_numpy=True).tolist()

# --- 2. POMOCNÉ FUNKCE ---

def extract_search_params(text):
    """Vytáhne z textu číslo linky a datum, doplní rok 2026."""
    line_match = re.search(r'(?:linka\s+|č\.\s*|bus\s*)?(\d{1,3})', text.lower())
    line = int(line_match.group(1)) if line_match else None

    date_match = re.search(r'(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?', text)
    date_str = None
    if date_match:
        den = int(date_match.group(1))
        mesic = int(date_match.group(2))
        rok = 2026 # Natvrdo nastavený rok dle zadání
        date_str = f"{den:02d}.{mesic:02d}.{rok}"

    return line, date_str

def clean_and_parse_json(filepath):
    """Načte a opraví JSON pole ze souboru."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start = content.find('[')
    end = content.rfind(']')
    if start == -1 or end == -1: return []
    json_str = content[start : end + 1]
    json_str = re.sub(r',\s*\]', ']', json_str)
    json_str = re.sub(r',\s*\}', '}', json_str)
    try:
        return json.loads(json_str)
    except:
        json_str = json_str.replace('}\n', '},\n').replace('}{', '},{')
        try: return json.loads(json_str)
        except: return []

def flatten_metadata(meta):
    """Zploští vnořené slovníky pro ChromaDB."""
    flat = {}
    for k, v in meta.items():
        if isinstance(v, dict):
            for sk, sv in v.items(): flat[f"{k}_{sk}"] = str(sv)
        elif isinstance(v, list): flat[k] = str(v)
        else: flat[k] = v
    return flat

def extract_sekvence(item, linka):
    """Pokusí se vytáhnout oběh/sekvenci z metadat nebo dokumentu."""
    meta = item.get('metadata', {})
    
    sekvence = str(meta.get('sekvence', meta.get('obeh', '')))
    if sekvence and sekvence.strip():
        return sekvence.strip()
    
    doc = item.get('document', '')
    m = re.search(rf'linka\s+{linka}\s+(.*?)\s+zpoždění', doc)
    if m:
        extracted = m.group(1).strip()
        if extracted: return extracted
        
    return "Neznámá"

# --- 3. HLAVNÍ LOGIKA ---

def main():
    print(f"Hledám JSON záznamy ve složce: {DATA_DIR}")
    
    if not os.path.exists(DATA_DIR):
        print(f"❌ Složka {DATA_DIR} neexistuje.")
        return
        
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    if not json_files:
        print("ℹ️ Ve složce nebyly nalezeny žádné nové JSON soubory ke zpracování.")
        return

    # A. Zpracování a Deduplikace
    best_records = {} 
    total_raw_records = 0

    for filepath in json_files:
        print(f"Čtu: {os.path.basename(filepath)}")
        raw_data = clean_and_parse_json(filepath)
        
        file_items = []
        def recursive_flatten(item):
            if isinstance(item, list):
                for i in item: recursive_flatten(i)
            else: file_items.append(item)
        recursive_flatten(raw_data)
        
        total_raw_records += len(file_items)

        for item in file_items:
            if not isinstance(item, dict) or 'id' not in item: continue
            
            meta = item.get('metadata', {})
            den = meta.get('den', 'Neznámý_den')
            linka = str(meta.get('linka', '0'))
            prijezd = meta.get('prijezd', '')
            hodina = prijezd.split(':')[0] if prijezd else '00'
            
            try:
                zpozdeni = float(meta.get('zpozdeni', 0))
            except (ValueError, TypeError):
                zpozdeni = 0
                
            sekvence = extract_sekvence(item, linka)
            key = (den, linka, sekvence, hodina)
            
            if key not in best_records:
                best_records[key] = item
            else:
                current_best = best_records[key]
                try:
                    current_zpozdeni = float(current_best.get('metadata', {}).get('zpozdeni', 0))
                except (ValueError, TypeError):
                    current_zpozdeni = 0
                    
                if zpozdeni > current_zpozdeni:
                    best_records[key] = item

    print("-" * 50)
    print(f"Celkem načteno hrubých záznamů: {total_raw_records}")
    print(f"Unikátní kandidáti k zápisu: {len(best_records)}")
    print("-" * 50)

    if not best_records:
        print("Žádná platná data k importu.")
        return

    # B. ChromaDB & Model (Perzistentní připojení)
    print(f"Připojuji se k ChromaDB: {DB_PATH}")
    client = chromadb.PersistentClient(path=DB_PATH)
    ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    # C. Import s podmíněným upsertem
    ids_to_upsert, docs_to_upsert, metas_to_upsert = [], [], []
    skipped_count = updated_count = new_count = 0

    print("Kontroluji existující záznamy v databázi a porovnávám zpoždění...")

    for key, item in best_records.items():
        den, linka, sekvence, hodina = key
        
        safe_den = den.replace('.', '')
        safe_sekvence = sekvence.replace(' ', '_')
        unique_id = f"{safe_den}_L{linka}_S{safe_sekvence}_H{hodina}"
        
        try:
            new_zpozdeni = float(item.get('metadata', {}).get('zpozdeni', 0))
        except (ValueError, TypeError):
            new_zpozdeni = 0

        existing_record = collection.get(ids=[unique_id])
        should_upsert = False
        
        if existing_record and existing_record['ids']:
            existing_metas = existing_record['metadatas'][0]
            try:
                existing_zpozdeni = float(existing_metas.get('zpozdeni', 0))
            except (ValueError, TypeError):
                existing_zpozdeni = 0
                
            if new_zpozdeni > existing_zpozdeni:
                should_upsert = True
                updated_count += 1
            else:
                skipped_count += 1
        else:
            should_upsert = True
            new_count += 1
            
        if should_upsert:
            ids_to_upsert.append(unique_id)
            docs_to_upsert.append(item.get('document', item.get('query', '')))
            metas_to_upsert.append(flatten_metadata(item.get('metadata', {})))
            
            if len(ids_to_upsert) >= 50:
                collection.upsert(ids=ids_to_upsert, documents=docs_to_upsert, metadatas=metas_to_upsert)
                ids_to_upsert, docs_to_upsert, metas_to_upsert = [], [], []

    if ids_to_upsert: 
        collection.upsert(ids=ids_to_upsert, documents=docs_to_upsert, metadatas=metas_to_upsert)
    
    print("-" * 50)
    print(f"✅ Aktualizace ChromaDB dokončena.")
    print(f"   Nových záznamů: {new_count}")
    print(f"   Aktualizovaných (delší zpoždění): {updated_count}")
    print(f"   Přeskočených (stejné/menší zpoždění): {skipped_count}")
    print("-" * 50)

    # D. Přesun zpracovaných souborů
    print("\n📦 Úklid: Přesouvám zpracované JSON soubory...")
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    for filepath in json_files:
        filename = os.path.basename(filepath)
        dest_path = os.path.join(PROCESSED_DIR, filename)
        try:
            # Pokud soubor v archivu už existuje, přepíšeme ho (zamezí pádům skriptu)
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(filepath, dest_path)
            print(f"   -> Přesunuto: {filename}")
        except Exception as e:
            print(f"   ❌ Chyba při přesunu {filename}: {e}")

    # G. TESTOVACÍ CYKLUS
    testovaci_dotazy = [
        "Jaké měla zpoždění linka 177 dne  4.3. ?",
        "Jaké měla zpoždění linka 180 dne  3.3. ?",
        "Jaké měla zpoždění linka 136 dne 16.2. ?",
        "Zpoždění linky 128 dne 15.2. - nemá být žádné"
    ]

    print("\n" + "="*50)
    print("SPOUŠTÍM TESTOVACÍ CYKLUS")
    print("="*50)

    for dotaz in testovaci_dotazy:
        print(f"\n>>> DOTAZ: '{dotaz}'")
        
        line, day = extract_search_params(dotaz)
        
        if not line or not day:
            print("❌ Nepodařilo se detekovat linku nebo datum.")
            continue

        results = collection.query(
            query_texts=[dotaz],
            n_results=2,
            where={
                "$and": [
                    {"linka": {"$eq": line}},
                    {"den": {"$eq": day}}
                ]
            }
        )

        found_docs = results['documents'][0] if results['documents'] else []
        found_metas = results['metadatas'][0] if results['metadatas'] else []

        if not found_docs:
            print(f"Nenalezeny zpoždění linky {line} pro den {day}")
            print("❌ NENALEZENO.")
        else:
            print(f"✅ NALEZENO {len(found_docs)} záznamů:")
            for i in range(len(found_docs)):
                print(f"   [{i+1}] {found_docs[i]}")
                p = found_metas[i]
                pricina = p.get('detail_priciny', p.get('pricina', 'Neznámá'))
                print(f"       Příčina: {pricina}")

if __name__ == "__main__":
    main()