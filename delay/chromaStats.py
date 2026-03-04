import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
import os
import time
import sys
import numpy as np # Přidáme pro jistotu, kdybychom chtěli pracovat s typy

# --- KONFIGURACE ---
DB_PATH = r"C:\AI\aJizdniVykony\delay\chroma_db"
COLLECTION_NAME = "delays"
MODEL_PATH = r"C:\AI\models\paraphrase-multilingual-MiniLM-L12-v2"

# --- DEFINICE TŘÍDY PRO EMBEDDING ---
class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path):
        try:
            self.model = SentenceTransformer(model_path)
        except Exception as e:
            print(f"Chyba modelu: {e}")
            raise e

    def __call__(self, input: Documents) -> Embeddings:
        # Zajistíme převod na list, aby to ChromaDB spolkla
        return self.model.encode(input, convert_to_numpy=True).tolist()

def get_dir_size(path):
    """Vypočítá skutečnou velikost složky na disku."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

def format_bytes(size):
    """Převede byty na KB/MB."""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def main():
    print("==================================================")
    print("          STATISTIKA CHROMADB EMBEDDINGS          ")
    print("==================================================")

    # 1. PŘIPOJENÍ
    print(f"-> Připojuji se k DB: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("CHYBA: Databáze neexistuje.")
        return

    client = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)
        collection = client.get_collection(name=COLLECTION_NAME, embedding_function=ef)
    except Exception as e:
        print(f"CHYBA: Nelze načíst kolekci '{COLLECTION_NAME}'.")
        print(f"Detail: {e}")
        return

    # 2. ZÁKLADNÍ POČTY
    count = collection.count()
    print(f"\n[1] POČET ZÁZNAMŮ")
    print(f"    Celkem vektorů v DB:  {count}")

    if count == 0:
        print("    Databáze je prázdná.")
        return

    # 3. ANALÝZA VEKTORŮ (VELIKOST)
    # Stáhneme jeden vektor pro analýzu dimenze
    sample = collection.peek(limit=1)
    embeddings = sample.get('embeddings')
    
    # --- ZDE BYLA CHYBA (OPRAVENO) ---
    # Kontrolujeme explicitně na None, abychom se vyhnuli NumPy chybě
    if embeddings is not None and len(embeddings) > 0:
        vector = embeddings[0] # První vektor
        dim = len(vector)      # Počet dimenzí (např. 384)
        
        # Float32 zabírá 4 byty
        bytes_per_vector = dim * 4 
        total_raw_bytes = bytes_per_vector * count
        
        print(f"\n[2] VLASTNOSTI VEKTORŮ (EMBEDDINGS)")
        print(f"    Dimenze modelu:       {dim} čísel na jeden vektor")
        print(f"    Velikost 1 vektoru:   {bytes_per_vector} bytů (raw float32)")
        print(f"    Teoretická RAM data:  {format_bytes(total_raw_bytes)} (pouze vektory)")
    else:
        print("\n[2] VLASTNOSTI VEKTORŮ")
        print("    Nelze načíst vzorek vektorů (možná chyba v peeking).")
    
    # 4. SKUTEČNÁ VELIKOST NA DISKU
    disk_size = get_dir_size(DB_PATH)
    print(f"\n[3] VELIKOST NA DISKU")
    print(f"    Složka 'chroma_db':   {format_bytes(disk_size)}")
    print(f"    (Obsahuje: indexy, metadata, texty a režii DB)")

    # 5. TEST RYCHLOSTI QUERY (KROKY)
    print(f"\n[4] ANALÝZA QUERY (Hledání)")
    query_text = "zpoždění autobusů"
    
    start_time = time.time()
    results = collection.query(
        query_texts=[query_text],
        n_results=10 if count >= 10 else count
    )
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"    Dotaz:                '{query_text}'")
    print(f"    Doba vyhledávání:     {duration:.4f} sekund")
    
    if results['distances'] and len(results['distances'][0]) > 0:
        distances = results['distances'][0]
        best_dist = min(distances)
        worst_dist = max(distances)
        print(f"    Nejlepší shoda (dist):{best_dist:.4f}")
        print(f"    Počet vrácených:      {len(distances)}")
    else:
        print("    Žádné výsledky nevráceny.")

    print("\n==================================================")

if __name__ == "__main__":
    main()