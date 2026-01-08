import chromadb
from chromadb.config import Settings
import os

# Path to ChromaDB
chroma_path = os.path.join('data', 'chroma')

# Initialize client
client = chromadb.PersistentClient(
    path=chroma_path,
    settings=Settings(anonymized_telemetry=False)
)
collection = client.get_collection(name="knowledge_chunks")

# Test Queries
queries = ["李昭賢", "Docker基礎", "HTML語法", "這是一份關於網頁設計的投影片"]

print(f"Testing queries on collection with {collection.count()} chunks...\n")

for query in queries:
    print(f"🔍 Query: '{query}'")
    results = collection.query(
        query_texts=[query], # Chroma will use the default embedding function if not provided
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
