import chromadb

# --- KONFIGURACE ---
DB_PATH = r"C:\AI\aJizdniVykony\delay\chroma_db"
COLLECTION_NAME = "delays"

HLEDANA_LINKA_STR = "177" 
HLEDANA_LINKA_INT = 177

def main():
    print(f"Připojuji se k databázi: {DB_PATH}")
    client = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except ValueError:
        print(f"❌ Kolekce '{COLLECTION_NAME}' neexistuje.")
        return

    print(f"Hledám všechny záznamy pro linku 177 (jako text i jako číslo)...")

    # Používáme operátor $or pro vyhledání textu NEBO čísla
    results = collection.get(
        where={
            "$or": [
                {"linka": HLEDANA_LINKA_STR},
                {"linka": HLEDANA_LINKA_INT}
            ]
        }
    )

    docs = results.get('documents', [])
    metas = results.get('metadatas', [])

    if not docs:
        print("Nebyly nalezeny žádné záznamy pro tuto linku.")
        return

    print("=" * 60)
    print(f"✅ NALEZENO ZÁZNAMŮ: {len(docs)}")
    print("=" * 60)

    for i in range(len(docs)):
        doc_text = docs[i]
        meta = metas[i]
        
        den = meta.get('den', 'Neznámý den')
        zpozdeni = meta.get('zpozdeni', '0')
        sekvence = meta.get('sekvence', meta.get('obeh', 'Neznámá'))
        
        print(f"[{i+1}] {doc_text}")
        print(f"    ▶ Datum: {den}")
        print(f"    ▶ Zpoždění: {zpozdeni} min")
        print(f"    ▶ Sekvence/Oběh: {sekvence}")
        print("-" * 60)

if __name__ == "__main__":
    main()