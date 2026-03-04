import json
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
import os
import re
from datetime import datetime

# --- KONFIGURACE ---
INPUT_FILE = r"C:\AI\aJizdniVykony\delay\data\15febALL.json"
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
    # Hledání linky (1-3 číslice)
    line_match = re.search(r'(?:linka\s+|č\.\s*|bus\s*)?(\d{1,3})', text.lower())
    line = int(line_match.group(1)) if line_match else None

    # Hledání data (DD.MM. nebo DD. MM.)
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
    
    #print(f"content  {content} ")

    start = content.find('[')
    end = content.rfind(']')
    if start == -1 or end == -1: return []
    json_str = content[start : end + 1]
    json_str = re.sub(r',\s*\]', ']', json_str)
    json_str = re.sub(r',\s*\}', '}', json_str)
    try:
        #print(f"json_str  {json_str} ")
        return json.loads(json_str)
    except:
        json_str = json_str.replace('}\n', '},\n').replace('}{', '},{')
        try: return json.loads(json_str)
        except: return []


def flatten_metadata(meta):
    flat = {}
    for k, v in meta.items():
        if isinstance(v, dict):
            for sk, sv in v.items(): flat[f"{k}_{sk}"] = str(sv)
        elif isinstance(v, list): flat[k] = str(v)
        else: flat[k] = v
    return flat

# --- 3. HLAVNÍ LOGIKA ---

def main():
    # A. Data
    print(f"Import záznamů z: {INPUT_FILE}  -> ChromaDB: {DB_PATH} -> Kolekce: {COLLECTION_NAME}")
    
    raw_data = clean_and_parse_json(INPUT_FILE)
    
    if not raw_data: return
    print(f"Načteno {len(raw_data)} záznamů (včetně vnořených). Zplošťuji seznam...")
    # Zploštění seznamu (pokud jsou vnořené)
    data_list = []
    def recursive_flatten(item):
        if isinstance(item, list):
            for i in item: recursive_flatten(i)
        else: data_list.append(item)
    recursive_flatten(raw_data)

    # B. ChromaDB & Model
    client = chromadb.PersistentClient(path=DB_PATH)
    ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
    except: pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    # C. Import
    ids, docs, metas = [], [], []
    for item in data_list:
        if not isinstance(item, dict) or 'id' not in item: continue
        ids.append(str(item['id']))
        docs.append(item.get('document', item.get('query', '')))
        metas.append(flatten_metadata(item.get('metadata', {})))
        
        if len(ids) >= 50:
            collection.upsert(ids=ids, documents=docs, metadatas=metas)
            ids, docs, metas = [], [], []

    if ids: collection.upsert(ids=ids, documents=docs, metadatas=metas)
    print(f"Importováno {collection.count()} záznamů.")

    # G. TESTOVACÍ CYKLUS (3 DOTAZY)
    #    "Jaké měla zpoždění linka 348 dne 15.2. ?",
    #   "Jaké měla zpoždění linka 116 dne 15.2. ?",
    #    "Měla linka 125 zpoždění 16.2. ?",
    #    "Zpoždění linky 911 dne 15.2. ?",
    #    "Jaké měla zpoždění linka 348 dne 11.2. ?",
    testovaci_dotazy = [
        "Jaké měla zpoždění linka 136 dne 1.2. ?",
        "Zpoždění linky 128 dne 15.2."
    ]

    print("\n" + "="*50)
    print("SPOUŠTÍM TESTOVACÍ CYKLUS")
    print("="*50)

    for dotaz in testovaci_dotazy:
        print(f"\n>>> DOTAZ: '{dotaz}'")
        
        # Automatická extrakce parametrů z textu
        line, day = extract_search_params(dotaz)
        
        if not line or not day:
            print("❌ Nepodařilo se detekovat linku nebo datum.")
            continue

        # Vyhledávání s filtry
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