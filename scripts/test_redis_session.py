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


# Import after adding the project root.
from services.session_store import (
    append_message,
    clear_session,
    create_session_id,
    get_session_history,
    get_storage_backend,
)


# ---------------------------------------------------------
# TEST REDIS SESSION STORAGE
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Starting Redis session test.")

    backend = get_storage_backend()

    print(
        f"Storage backend: {backend}"
    )

    assert backend == "redis", (
        "Redis is not being used. "
        f"Current backend: {backend}"
    )

    session_id = create_session_id()

    print(
        f"Created session: {session_id}"
    )

    append_message(
        session_id=session_id,
        role="user",
        content="Show the lowest salary",
    )

    append_message(
        session_id=session_id,
        role="assistant",
        content=(
            "The lowest salary result "
            "was returned successfully."
        ),
    )

    history = get_session_history(
        session_id
    )

    print(
        f"Messages found: {len(history)}"
    )

    for message in history:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )

    assert len(history) == 2

    assert history[0]["role"] == "user"

    assert history[1]["role"] == "assistant"

    clear_session(
        session_id
    )

    history_after_clear = (
        get_session_history(session_id)
    )

    assert history_after_clear == []

    print(
        "Session cleared successfully."
    )

    print(
        "All Redis session tests passed."
    )