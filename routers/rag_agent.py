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
POLICY_COLLECTION_NAME = (
    "hr_policies"
)

CONTEXT_COLLECTION_NAME = (
    "hr_context"
)


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


def query_collection(
    *,
    client,
    collection_name: str,
    question: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """
    Query one ChromaDB collection.

    If that collection does not exist, return an
    empty list so the other collection can still work.
    """

    try:

        collection = client.get_collection(
            name=collection_name
        )

    except Exception:
        return []

    collection_count = (
        collection.count()
    )

    if collection_count == 0:
        return []

    query_results = collection.query(

        query_texts=[
            question
        ],

        n_results=min(
            top_k,
            collection_count,
        ),
    )

    documents = (
        query_results.get(
            "documents",
            [[]],
        )[0]
    )

    metadatas = (
        query_results.get(
            "metadatas",
            [[]],
        )[0]
    )

    retrieved_chunks = []

    for document, metadata in zip(
        documents,
        metadatas,
    ):

        retrieved_chunks.append(
            {
                "text": document,

                "source": metadata.get(
                    "source",
                    collection_name,
                ),

                "chunk_index": int(
                    metadata.get(
                        "chunk_index",
                        -1,
                    )
                ),

                "context_type": (
                    metadata.get(
                        "context_type",
                        "policy",
                    )
                ),

                "priority": int(
                    metadata.get(
                        "priority",
                        0,
                    )
                ),
            }
        )

    return retrieved_chunks


def retrieve_policy_chunks(
    question: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """
    Search the YAML context collection and the
    original policy collection.

    Approved feedback has the highest priority.
    """

    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_DIR)
    )

    context_chunks = query_collection(

        client=client,

        collection_name=(
            CONTEXT_COLLECTION_NAME
        ),

        question=question,

        top_k=2,
    )

    policy_chunks = query_collection(

        client=client,

        collection_name=(
            POLICY_COLLECTION_NAME
        ),

        question=question,

        top_k=top_k,
    )

    all_chunks = (
        context_chunks
        + policy_chunks
    )

    all_chunks.sort(
        key=lambda chunk: chunk.get(
            "priority",
            0,
        ),
        reverse=True,
    )

    if not all_chunks:

        raise HTTPException(
            status_code=500,
            detail=(
                "No RAG collections were found. "
                "Run the policy index builder and "
                "build_context_rag_index.py."
            ),
        )

    return all_chunks


def build_llama_prompt(
    question: str,
    chunks: list[dict[str, Any]],
) -> str:
    """
    Build a priority-aware RAG prompt.

    Priority order:

    approved feedback
    glossary/schema
    policy documents
    """

    context_sections = []

    for chunk in chunks:

        context_section = (
            f"Priority: "
            f"{chunk.get('priority', 0)}\n"

            f"Context type: "
            f"{chunk.get('context_type', 'policy')}\n"

            f"Source: "
            f"{chunk.get('source', 'unknown')}\n"

            f"Content:\n"
            f"{chunk.get('text', '')}"
        )

        context_sections.append(
            context_section
        )

    combined_context = "\n\n".join(
        context_sections
    )

    return f"""
You are the customer-facing HR Agent.

Answer using only the supplied context.

Context priority:
1. Approved feedback corrections
2. HR glossary and schema mappings
3. HR policy documents

When sources conflict, use the source with the
higher numeric priority.

Do not invent employee data, policy information,
salary details or database facts.

If the answer is not available, say exactly:

"I could not find that information in the available HR context."

Do not return:
- JSON
- SQL
- internal agent names
- internal routing information
- hidden reasoning
- source dictionaries

Context:
{combined_context}

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
                context_type=chunk.get(
            "context_type",
            "policy",
        ),
        priority=chunk.get(
            "priority",
            0,
        ),
     )
     for chunk in chunks
     ],
    )