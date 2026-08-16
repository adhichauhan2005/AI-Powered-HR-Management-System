from __future__ import annotations

from pathlib import Path
from typing import Any

import json

import chromadb
import yaml


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

CONTEXT_DIR = (
    PROJECT_ROOT
    / "context"
)

CHROMA_DB_DIR = (
    PROJECT_ROOT
    / "chroma_db"
)

CONTEXT_COLLECTION_NAME = (
    "hr_context"
)


# ---------------------------------------------------------
# YAML LOADER
# ---------------------------------------------------------

def load_yaml_file(
    file_path: Path,
) -> dict[str, Any]:
    """
    Safely load a YAML file.
    """

    if not file_path.exists():
        return {}

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        yaml_data = yaml.safe_load(
            file
        )

    if yaml_data is None:
        return {}

    return yaml_data


# ---------------------------------------------------------
# GLOSSARY DOCUMENTS
# ---------------------------------------------------------

def build_glossary_documents() -> list[
    dict[str, Any]
]:
    """
    Convert every glossary term into a text document
    that can be indexed in ChromaDB.
    """

    glossary_path = (
        CONTEXT_DIR
        / "hr_glossary.yaml"
    )

    glossary_data = load_yaml_file(
        glossary_path
    )

    glossary_terms = glossary_data.get(
        "terms",
        {},
    )

    documents = []

    for (
        canonical_name,
        details,
    ) in glossary_terms.items():

        aliases = details.get(
            "aliases",
            [],
        )

        examples = details.get(
            "examples",
            [],
        )

        table = details.get(
            "table",
            details.get(
                "structured_table",
                "",
            ),
        )

        column = details.get(
            "column",
            details.get(
                "key_column",
                "",
            ),
        )

        document_text = (
            f"Canonical HR term: {canonical_name}. "
            f"Aliases: {', '.join(aliases)}. "
            f"Meaning: {details.get('meaning', '')}. "
            f"Entity type: "
            f"{details.get('entity_type', '')}. "
            f"Database table: {table}. "
            f"Database column: {column}. "
            f"Examples: {' | '.join(examples)}."
        )

        documents.append(
            {
                "id": (
                    f"glossary-"
                    f"{canonical_name}"
                ),

                "text": document_text,

                "metadata": {
                    "source": (
                        "hr_glossary.yaml"
                    ),

                    "context_type": (
                        "glossary"
                    ),

                    # Feedback will have higher priority.
                    "priority": 50,
                },
            }
        )

    return documents


# ---------------------------------------------------------
# FEEDBACK DOCUMENTS
# ---------------------------------------------------------

def build_feedback_documents() -> list[
    dict[str, Any]
]:
    """
    Convert approved feedback corrections into
    ChromaDB documents.
    """

    feedback_path = (
        CONTEXT_DIR
        / "feedback_overrides.yaml"
    )

    feedback_data = load_yaml_file(
        feedback_path
    )

    feedback_items = feedback_data.get(
        "overrides",
        [],
    )

    documents = []

    for index, feedback_item in enumerate(
        feedback_items
    ):

        if (
            feedback_item.get("status")
            != "approved"
        ):
            continue

        question = feedback_item.get(
            "question",
            "",
        )

        expected_answer = (
            feedback_item.get(
                "expected_answer",
                "",
            )
        )

        correction = feedback_item.get(
            "correction",
            {},
        )

        document_text = (
            "Approved HR Agent correction. "
            f"Question: {question}. "
            f"Expected answer: "
            f"{expected_answer}. "
            f"Correction details: "
            f"{json.dumps(correction)}."
        )

        documents.append(
            {
                "id": (
                    f"feedback-{index}"
                ),

                "text": document_text,

                "metadata": {
                    "source": (
                        "feedback_overrides.yaml"
                    ),

                    "context_type": (
                        "approved_feedback"
                    ),

                    # Feedback has the highest priority.
                    "priority": 100,
                },
            }
        )

    return documents


# ---------------------------------------------------------
# SCHEMA DOCUMENT
# ---------------------------------------------------------

def build_schema_documents() -> list[
    dict[str, Any]
]:
    """
    Add schema_mapping.yaml as contextual knowledge.
    """

    schema_path = (
        CONTEXT_DIR
        / "schema_mapping.yaml"
    )

    schema_data = load_yaml_file(
        schema_path
    )

    if not schema_data:
        return []

    document_text = (
        "HR database schema and semantic mapping. "
        + json.dumps(
            schema_data,
            default=str,
        )
    )

    return [
        {
            "id": "schema-mapping",

            "text": document_text,

            "metadata": {
                "source": (
                    "schema_mapping.yaml"
                ),

                "context_type": (
                    "schema_mapping"
                ),

                "priority": 60,
            },
        }
    ]


# ---------------------------------------------------------
# QUERY-RULE DOCUMENT
# ---------------------------------------------------------

def build_query_rule_documents() -> list[
    dict[str, Any]
]:
    """
    Add deterministic query rules to ChromaDB.
    """

    query_rules_path = (
        CONTEXT_DIR
        / "query_rules.yaml"
    )

    query_rules_data = load_yaml_file(
        query_rules_path
    )

    if not query_rules_data:
        return []

    document_text = (
        "HR Agent deterministic query rules. "
        + json.dumps(
            query_rules_data,
            default=str,
        )
    )

    return [
        {
            "id": "query-rules",

            "text": document_text,

            "metadata": {
                "source": (
                    "query_rules.yaml"
                ),

                "context_type": (
                    "query_rules"
                ),

                "priority": 70,
            },
        }
    ]


# ---------------------------------------------------------
# ALL CONTEXT DOCUMENTS
# ---------------------------------------------------------

def build_all_context_documents() -> list[
    dict[str, Any]
]:
    """
    Collect every context document before indexing.
    """

    documents = []

    documents.extend(
        build_glossary_documents()
    )

    documents.extend(
        build_feedback_documents()
    )

    documents.extend(
        build_schema_documents()
    )

    documents.extend(
        build_query_rule_documents()
    )

    return documents


# ---------------------------------------------------------
# CHROMADB INDEX BUILDER
# ---------------------------------------------------------

def build_context_rag_index() -> int:
    """
    Rebuild the hr_context ChromaDB collection.

    This does not delete the existing hr_policies
    collection.
    """

    CHROMA_DB_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_DIR)
    )

    # Delete only the context collection.
    #
    # The existing HR policy collection remains.
    try:

        client.delete_collection(
            name=CONTEXT_COLLECTION_NAME
        )

    except Exception:
        # The collection may not exist during
        # the first build.
        pass

    context_collection = (
        client.create_collection(
            name=CONTEXT_COLLECTION_NAME
        )
    )

    documents = (
        build_all_context_documents()
    )

    if not documents:
        return 0

    context_collection.add(

        ids=[
            document["id"]
            for document in documents
        ],

        documents=[
            document["text"]
            for document in documents
        ],

        metadatas=[
            document["metadata"]
            for document in documents
        ],
    )

    return len(documents)