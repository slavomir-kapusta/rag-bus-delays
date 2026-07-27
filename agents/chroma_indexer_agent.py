"""
ChromaDB Indexer Agent
File: agents/chroma_indexer_agent.py
Task Type: index-chromadb
"""

import os
import re
import json
import glob
import shutil
import asyncio
from datetime import datetime
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
from pyzeebe import ZeebeWorker, create_insecure_channel

# System Paths
BASE_DIR = r"D:\AI\aJizdniVykony\delay"
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
DB_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "delays"
MODEL_PATH = r"C:\AI\models\paraphrase-multilingual-MiniLM-L12-v2"

class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path):
        print(f"Initializing SentenceTransformer from: {model_path}")
        try:
            self.model = SentenceTransformer(model_path)
        except Exception as e:
            print(f"CRITICAL ERROR loading model: {e}")
            raise e

    def __call__(self, input: Documents) -> Embeddings:
        return self.model.encode(input, convert_to_numpy=True).tolist()

def clean_and_parse_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start = content.find('[')
    end = content.rfind(']')
    if start == -1 or end == -1:
        return []
    json_str = content[start : end + 1]
    json_str = re.sub(r',\s*\]', ']', json_str)
    json_str = re.sub(r',\s*\}', '}', json_str)
    try:
        return json.loads(json_str)
    except Exception:
        json_str = json_str.replace('}\n', '},\n').replace('}{', '},{')
        try:
            return json.loads(json_str)
        except Exception:
            return []

def flatten_metadata(meta):
    flat = {}
    for k, v in meta.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                flat[f"{k}_{sk}"] = str(sv)
        elif isinstance(v, list):
            flat[k] = str(v)
        else:
            flat[k] = v
    return flat

def extract_sekvence(item, linka):
    meta = item.get('metadata', {})
    sekvence = str(meta.get('sekvence', meta.get('obeh', '')))
    if sekvence and sekvence.strip():
        return sekvence.strip()
    
    doc = item.get('document', '')
    m = re.search(rf'linka\s+{linka}\s+(.*?)\s+zpoždění', doc)
    if m:
        extracted = m.group(1).strip()
        if extracted:
            return extracted
    return "Neznámá"

def run_indexing():
    if not os.path.exists(DATA_DIR):
        return {"status": "NO_DATA_DIR", "indexed": 0}

    # Locate JSON files excluding the processed directory
    json_files = [f for f in glob.glob(os.path.join(DATA_DIR, "*.json")) if os.path.isfile(f)]
    if not json_files:
        return {"status": "NO_FILES", "indexed": 0}

    best_records = {}
    total_raw_records = 0

    for filepath in json_files:
        raw_data = clean_and_parse_json(filepath)
        file_items = []
        
        def recursive_flatten(item):
            if isinstance(item, list):
                for i in item:
                    recursive_flatten(i)
            else:
                file_items.append(item)
                
        recursive_flatten(raw_data)
        total_raw_records += len(file_items)

        for item in file_items:
            if not isinstance(item, dict) or 'id' not in item:
                continue
            
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

    if not best_records:
        return {"status": "NO_VALID_RECORDS", "indexed": 0}

    # Initialize ChromaDB client and embedding function
    client = chromadb.PersistentClient(path=DB_PATH)
    ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    ids_to_upsert, docs_to_upsert, metas_to_upsert = [], [], []
    new_count = updated_count = skipped_count = 0

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

    # Move processed JSON files to archive
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    for filepath in json_files:
        filename = os.path.basename(filepath)
        dest_path = os.path.join(PROCESSED_DIR, filename)
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(filepath, dest_path)
        except Exception as e:
            print(f"Error archiving {filename}: {e}")

    return {
        "status": "SUCCESS",
        "newRecords": new_count,
        "updatedRecords": updated_count,
        "skippedRecords": skipped_count
    }

async def main():
    channel = create_insecure_channel(hostname="localhost", port=26500)
    worker = ZeebeWorker(channel)

    @worker.task(task_type="index-chromadb")
    def handle_chroma_index():
        print("\n[ChromaIndexerAgent] Starting vector store indexing...")
        result = run_indexing()
        print(f"[ChromaIndexerAgent] Finished. Result: {result}")
        return {"chromaIndexResult": result}

    print("Agent [ChromaIndexerAgent] listening on port 26500...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())