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

# Get collection
collection = client.get_collection(name="knowledge_chunks")

print(f"Collection count: {collection.count()}")

# Get some data
results = collection.peek(limit=5)
for i in range(len(results['ids'])):
    print(f"ID: {results['ids'][i]}")
    print(f"Document preview: {results['documents'][i][:100]}...")
    print(f"Metadata: {results['metadatas'][i]}")
    print("-" * 20)
