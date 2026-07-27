"""
Golemio Transport Intelligence MCP Server
File: agents/mcp_server.py
"""

import os
import re
import json
from datetime import datetime
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GolemioTransportServer")

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

@mcp.tool()
def query_chromadb_rag(natural_query: str) -> str:
    """Executes a RAG vector search on ChromaDB filtering by line number and date extracted from query."""
    if not os.path.exists(DB_PATH):
        return json.dumps({"error": "ChromaDB store not found."})

    client = chromadb.PersistentClient(path=DB_PATH)
    ef = LocalSentenceTransformerEmbeddingFunction(MODEL_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    line, day = extract_search_params(natural_query)
    if not line or not day:
        return json.dumps({"error": "Could not extract bus line number or date from query."})

    results = collection.query(
        query_texts=[natural_query],
        n_results=3,
        where={
            "$and": [
                {"linka": {"$eq": line}},
                {"den": {"$eq": day}}
            ]
        }
    )

    found_docs = results['documents'][0] if results['documents'] else []
    found_metas = results['metadatas'][0] if results['metadatas'] else []

    return json.dumps({
        "line": line,
        "day": day,
        "results_count": len(found_docs),
        "documents": found_docs,
        "metadatas": found_metas
    }, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    mcp.run()