import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
import os

# --- KONFIGURACE ---
DB_PATH = r"C:\AI\aJizdniVykony\delay\chroma_db"
COLLECTION_NAME = "delays"
# Cesta k vaší lokální složce
MODEL_PATH = r"C:\AI\models\paraphrase-multilingual-MiniLM-L12-v2"

# --- VLASTNÍ TŘÍDA PRO EMBEDDING ---
# Tímto obejdeme chyby v defaultním wrapperu ChromaDB
class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path):
        print(f"   -> Inicializuji SentenceTransformer z: {model_path}")
        try:
            # Načteme model přímo přes knihovnu sentence_transformers
            self.model = SentenceTransformer(model_path)
        except Exception as e:
            print(f"\n!!! KRITICKÁ CHYBA PŘI NAČÍTÁNÍ MODELU !!!")
            print(f"Pravděpodobně chybí soubor 'modules.json' nebo 'config.json' ve složce.")
            print(f"Chyba: {e}")
            raise e

    def __call__(self, input: Documents) -> Embeddings:
        # Převedeme text na vektory (embeddings)
        # convert_to_numpy=True a .tolist() zajistí formát, který ChromaDB chce
        embeddings = self.model.encode(input, convert_to_numpy=True).tolist()
        return embeddings

def query_database():
    print(f"--- VYHLEDÁVÁNÍ V CHROMADB (Local Model) ---")
    
    # 1. Inicializace naší vlastní funkce
    try:
        ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)
    except:
        return # Konec, pokud se model nenačte

    # 2. Připojení k DB
    client = chromadb.PersistentClient(path=DB_PATH)

    # 3. Získání kolekce
    try:
        collection = client.get_collection(
            name=COLLECTION_NAME, 
            embedding_function=ef
        )
        print(f"-> Kolekce '{COLLECTION_NAME}' načtena. Počet záznamů: {collection.count()}")
    except Exception as e:
        print(f"CHYBA: Kolekce neexistuje. ({e})")
        print("Tip: Ujistěte se, že jste nejprve spustili 'finalImport.py' se stejným modelem.")
        return

    # --- DEFINICE DOTAZŮ ---
    questions = [
        "Které autobusy měly zpoždění kvůli počasí?",
        "Stala se 15. února nějaká dopravní nehoda?",
        "Jaké problémy byly na lince 125?"
    ]

    # 4. Provedení dotazů
    for q in questions:
        print(f"\n--------------------------------------------------")
        print(f"DOTAZ: '{q}'")
        
        results = collection.query(
            query_texts=[q],
            n_results=2  
        )

        ids = results['ids'][0]
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        distances = results['distances'][0]

        if not ids:
            print(" -> Žádná shoda nenalezena.")
            continue

        for i in range(len(ids)):
            print(f"\n   [Výsledek #{i+1}] (Distance: {distances[i]:.4f})")
            print(f"   ID: {ids[i]}")
            print(f"   Text: {docs[i]}")
            m = metas[i]
            # Pokusíme se vytáhnout příčinu z různých možných klíčů metadat
            pricina = m.get('detail_priciny', m.get('pricina', 'N/A'))
            print(f"   Příčina: {pricina}")

if __name__ == "__main__":
    query_database()