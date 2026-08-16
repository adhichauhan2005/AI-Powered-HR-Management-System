from pathlib import Path

import sys


# ---------------------------------------------------------
# ADD PROJECT ROOT TO PYTHON PATH
# ---------------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from services.context_rag_index import (
    CHROMA_DB_DIR,
    CONTEXT_COLLECTION_NAME,
    build_context_rag_index,
)


# ---------------------------------------------------------
# BUILD THE INDEX
# ---------------------------------------------------------

if __name__ == "__main__":

    print(
        "\nChromaDB location:"
    )

    print(
        CHROMA_DB_DIR
    )

    print(
        "\nContext collection:"
    )

    print(
        CONTEXT_COLLECTION_NAME
    )

    document_count = (
        build_context_rag_index()
    )

    print(
        "\nContext RAG index built "
        "successfully."
    )

    print(
        "Context documents indexed:",
        document_count,
    )