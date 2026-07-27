"""
RAG Delay Query Agent
File: agents/rag_query_agent.py
Task Type: rag-delay-query
"""

import os
import re
import json
import asyncio
from datetime import datetime
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
from pyzeebe import ZeebeWorker, create_insecure_channel

BASE_DIR = r"D:\AI\aJizdniVykony\delay"
DB_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "delays"
MODEL_PATH = r"C:\AI\models\paraphrase-multilingual-MiniLM-L12-v2"

class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path):
        self.model = SentenceTransformer(model_path)

    def __call__(self, input: Documents) -> Embeddings:
        return self.model.encode(input, convert_to_numpy=True).tolist()

def extract_search_params(text):
    """Extracts route number and date, assuming fixed year 2026."""
    line_match = re.search(r'(?:linka\s+|č\.\s*|bus\s*)?(\d{1,3})', text.lower())
    line = int(line_match.group(1)) if line_match else None

    date_match = re.search(r'(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?', text)
    date_str = None
    if date_match:
        den = int(date_match.group(1))
        mesic = int(date_match.group(2))
        rok = 2026
        date_str = f"{den:02d}.{mesic:02d}.{rok}"

    return line, date_str

def query_rag_database(query_text: str):
    if not os.path.exists(DB_PATH):
        return {"found": False, "error": "ChromaDB path does not exist."}

    client = chromadb.PersistentClient(path=DB_PATH)
    ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    line, day = extract_search_params(query_text)
    if not line or not day:
        return {"found": False, "error": "Failed to extract line number or date from query."}

    results = collection.query(
        query_texts=[query_text],
        n_results=5,
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
        return {
            "found": False,
            "line": line,
            "day": day,
            "message": f"No delays found for line {line} on {day}"
        }

    records = []
    for i in range(len(found_docs)):
        p = found_metas[i]
        records.append({
            "document": found_docs[i],
            "delay": p.get('zpozdeni'),
            "cause": p.get('detail_priciny', p.get('pricina', 'Neznámá')),
            "stop": p.get('zastavka'),
            "direction": p.get('smer')
        })

    return {
        "found": True,
        "line": line,
        "day": day,
        "count": len(found_docs),
        "records": records
    }

async def main():
    channel = create_insecure_channel(hostname="localhost", port=26500)
    worker = ZeebeWorker(channel)

    @worker.task(task_type="rag-delay-query")
    def handle_rag_query(searchQuery: str = None):
        print("\n[RAGDelayQueryAgent] Processing RAG delay inquiry...")
        
        # Default test query if none provided from process variables
        query = searchQuery or f"Jaké měla zpoždění linka 177 dne {datetime.now().strftime('%d.%m.')} ?"
        rag_response = query_rag_database(query)
        
        print(f"[RAGDelayQueryAgent] RAG Query Result: {rag_response}")
        return {"ragQueryResult": rag_response}

    print("Agent [RAGDelayQueryAgent] listening on port 26500...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())