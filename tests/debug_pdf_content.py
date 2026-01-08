import chromadb
from chromadb.config import Settings
import os

# Path to ChromaDB
chroma_path = os.path.join('data', 'chroma')

try:
    # Initialize client
    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=Settings(anonymized_telemetry=False)
    )

    # Get collection
    collection = client.get_collection(name="knowledge_chunks")

    # Target Document ID for "Web_Fall2024_單元01_網頁基礎.pdf"
    target_doc_id = "0af53a77bb01"

    print(f"Checking chunks for Document ID: {target_doc_id}")

    # Query specific document chunks
    results = collection.get(
        where={"document_id": target_doc_id},
        limit=5,
        include=["documents", "metadatas"]
    )

    if not results['ids']:
        print("❌ No chunks found for this document in ChromaDB.")
    else:
        print(f"✅ Found {len(results['ids'])} chunks (showing first 5).")
        for i in range(len(results['ids'])):
            print("-" * 40)
            print(f"Chunk ID: {results['ids'][i]}")
            print(f"Metadata: {results['metadatas'][i]}")
            print(f"Content Preview:\n{results['documents'][i][:200]}") # Show first 200 chars
            print("-" * 40)

except Exception as e:
    print(f"Error: {e}")
