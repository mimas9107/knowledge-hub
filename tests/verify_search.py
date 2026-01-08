import chromadb
from chromadb.config import Settings
import os
import sys

# Ensure we can import core modules
sys.path.append(os.getcwd())

from core.embedder import embed_text
from config import Config

# Path to ChromaDB
chroma_path = os.path.join('data', 'chroma')

# Initialize client
client = chromadb.PersistentClient(
    path=chroma_path,
    settings=Settings(anonymized_telemetry=False)
)
collection = client.get_collection(name="knowledge_chunks")

# Test Queries
queries = ["李昭賢", "Docker基礎", "HTML語法", "Vue.js", "網頁基礎"]

print(f"Testing queries using Project's Embedding Model: {Config.EMBEDDING_MODEL}")
print(f"Collection count: {collection.count()}\n")

for query in queries:
    print(f"🔍 Query: '{query}'")
    
    # 1. Generate embedding using the SAME model as ingestion
    query_embedding = embed_text(query)
    
    # 2. Query Chroma with the embedding
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        include=["documents", "metadatas", "distances"]
    )
    
    if results['ids']:
        for i in range(len(results['ids'][0])):
            distance = results['distances'][0][i]
            score = 1 / (1 + distance) # Convert distance to similarity score
            doc = results['documents'][0][i][:50].replace('\n', ' ')
            meta = results['metadatas'][0][i]
            filename = meta.get('filename', 'Unknown')
            
            print(f"   Score: {score:.4f} | File: {filename} | Text: {doc}...")
    else:
        print("   No results found.")
    print("-" * 50)
