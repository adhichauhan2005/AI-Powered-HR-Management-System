import os
from pathlib import Path
from typing import Any

import chromadb
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


load_dotenv()


router = APIRouter(
    prefix="/rag",
    tags=["RAG Agent"],
)


BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "hr_policies"


class RAGRequest(BaseModel):
    question: str


class RAGSource(BaseModel):
    source: str
    chunk_index: int
    text: str


class RAGResponse(BaseModel):
    question: str
    answer: str
    source_count: int
    sources: list[RAGSource]


def get_collection():
    """
    Connect to the local ChromaDB policy collection.
    """

    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_DIR)
    )

    try:
        return client.get_collection(
            name=COLLECTION_NAME
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "RAG index not found. Run build_rag_index.py first."
            ),
        ) from error


def retrieve_policy_chunks(
    question: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """
    Retrieve the most relevant policy chunks from ChromaDB.
    """

    collection = get_collection()

    results = collection.query(
        query_texts=[question],
        n_results=top_k,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    retrieved_chunks = []

    for document, metadata in zip(documents, metadatas):
        retrieved_chunks.append(
            {
                "text": document,
                "source": metadata.get("source", "unknown"),
                "chunk_index": metadata.get("chunk_index", -1),
            }
        )

    return retrieved_chunks


def build_llama_prompt(
    question: str,
    chunks: list[dict[str, Any]],
) -> str:
    """
    Create a prompt that forces Llama to answer only from context.
    """

    context = "\n\n".join(
        f"Source: {chunk['source']} | Chunk: {chunk['chunk_index']}\n"
        f"{chunk['text']}"
        for chunk in chunks
    )

    return f"""
You are an HR assistant.

Answer the user's question using only the context below.
If the answer is not present in the context, say:
"I could not find that information in the HR policy documents."

Context:
{context}

User question:
{question}

Answer:
"""


def call_ollama(prompt: str) -> str:
    """
    Ask local Llama to generate an answer from retrieved context.
    """

    ollama_base_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    ollama_model = os.getenv(
        "OLLAMA_MODEL",
        "llama3.2",
    )

    try:
        response = requests.post(
            f"{ollama_base_url}/api/generate",
            json={
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not connect to Ollama. "
                "Make sure Ollama is running."
            ),
        ) from error

    answer = response.json().get("response", "").strip()

    if not answer:
        raise HTTPException(
            status_code=500,
            detail="Ollama returned an empty answer.",
        )

    return answer


@router.post(
    "/ask",
    response_model=RAGResponse,
)
def ask_rag_agent(
    request: RAGRequest,
    top_k: int = Query(
        default=3,
        ge=1,
        le=5,
        description="Number of policy chunks to retrieve",
    ),
) -> RAGResponse:
    """
    Retrieve relevant HR policy chunks and generate an answer.
    """

    chunks = retrieve_policy_chunks(
        question=request.question,
        top_k=top_k,
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant policy chunks found.",
        )

    prompt = build_llama_prompt(
        question=request.question,
        chunks=chunks,
    )

    answer = call_ollama(prompt)

    return RAGResponse(
        question=request.question,
        answer=answer,
        source_count=len(chunks),
        sources=[
            RAGSource(
                source=chunk["source"],
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
            )
            for chunk in chunks
        ],
    )