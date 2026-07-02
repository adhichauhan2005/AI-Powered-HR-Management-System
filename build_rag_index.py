from pathlib import Path

import chromadb
from unstructured.partition.text import partition_text


BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
CHROMA_DB_DIR = BASE_DIR / "chroma_db"

COLLECTION_NAME = "hr_policies"


def load_policy_chunks() -> list[dict]:
    """
    Read HR policy text files and convert them into chunks.

    Each chunk will later be stored in ChromaDB.
    """

    chunks = []

    for file_path in KNOWLEDGE_BASE_DIR.glob("*.txt"):
        elements = partition_text(filename=str(file_path))

        for index, element in enumerate(elements):
            text = str(element).strip()

            if len(text) < 40:
                continue

            chunks.append(
                {
                    "id": f"{file_path.stem}_{index}",
                    "text": text,
                    "source": file_path.name,
                    "chunk_index": index,
                }
            )

    return chunks


def build_index() -> None:
    """
    Build a persistent ChromaDB index from HR policy documents.
    """

    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_DIR)
    )

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME
    )

    chunks = load_policy_chunks()

    if not chunks:
        raise RuntimeError(
            "No policy chunks found. Check knowledge_base folder."
        )

    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[
            {
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in chunks
        ],
    )

    print("RAG index created successfully.")
    print(f"Total chunks stored: {len(chunks)}")
    print(f"ChromaDB path: {CHROMA_DB_DIR}")


if __name__ == "__main__":
    build_index()