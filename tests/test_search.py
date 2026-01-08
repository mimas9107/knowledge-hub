import chromadb
from chromadb.config import Settings
import os
from sentence_transformers import SentenceTransformer

# Path to ChromaDB
chroma_path = os.path.join('data', 'chroma')

# Initialize client
client = chromadb.PersistentClient(path=chroma_path)
collection = client.get_collection(name="knowledge_chunks")

# Load model
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

query = "HTML"
query_embedding = model.encode(query).tolist()

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5,
    include=["documents", "metadatas", "distances"]
)

for i in range(len(results['ids'][0])):
    print(f"ID: {results['ids'][0][i]}")
    print(f"Distance: {results['distances'][0][i]}")
    print(f"Score (1/1+dist): {1 / (1 + results['distances'][0][i])}")
    print(f"Text: {results['documents'][0][i][:100]}...")
    print("-" * 20)
