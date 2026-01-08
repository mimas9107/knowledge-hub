import chromadb
from chromadb.config import Settings
import os

chroma_path = os.path.join('data', 'chroma')
client = chromadb.PersistentClient(path=chroma_path)
collection = client.get_collection(name="knowledge_chunks")

results = collection.get(
    where={"document_id": "e798c52b2805"},
    limit=10,
    include=["documents", "metadatas"]
)

for i in range(len(results['ids'])):
    print(f"ID: {results['ids'][i]}")
    print(f"Text: {results['documents'][i][:200]}")
    print("-" * 20)
