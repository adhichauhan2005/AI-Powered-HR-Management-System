"""
Redis-backed session storage for the HR Agent.

Redis stores the conversation history using the session ID
received from the frontend.

If Redis is unavailable and fallback is enabled, temporary
Python memory storage is used instead.
"""

from __future__ import annotations

import json
import os

from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from redis import Redis
from redis.exceptions import RedisError


# ---------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------------

load_dotenv()


SESSION_BACKEND = os.getenv(
    "SESSION_BACKEND",
    "redis",
).strip().lower()

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0",
)

REDIS_SESSION_TTL_SECONDS = int(
    os.getenv(
        "REDIS_SESSION_TTL_SECONDS",
        "86400",
    )
)

ALLOW_MEMORY_SESSION_FALLBACK = (
    os.getenv(
        "ALLOW_MEMORY_SESSION_FALLBACK",
        "true",
    ).strip().lower()
    == "true"
)


# ---------------------------------------------------------
# REDIS CLIENT
# ---------------------------------------------------------

_redis_client: Redis | None = None


def _get_redis_client() -> Redis:
    """
    Create the Redis client only when it is first needed.
    """

    global _redis_client

    if _redis_client is None:
        _redis_client = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )

    return _redis_client


def _redis_is_available() -> bool:
    """
    Check whether the application can communicate with Redis.
    """

    if SESSION_BACKEND == "memory":
        return False

    try:
        client = _get_redis_client()

        return bool(client.ping())

    except RedisError as error:
        if not ALLOW_MEMORY_SESSION_FALLBACK:
            raise ConnectionError(
                "Redis is unavailable and memory "
                "fallback is disabled."
            ) from error

        return False


# ---------------------------------------------------------
# MEMORY FALLBACK
# ---------------------------------------------------------

_MEMORY_SESSIONS: dict[
    str,
    list[dict[str, Any]],
] = {}

_MEMORY_LOCK = Lock()


# ---------------------------------------------------------
# SESSION KEY
# ---------------------------------------------------------

def _session_key(
    session_id: str,
) -> str:
    """
    Generate the Redis key for a session.
    """

    return (
        f"hr_agent:session:{session_id}"
    )


# ---------------------------------------------------------
# CREATE SESSION ID
# ---------------------------------------------------------

def create_session_id() -> str:
    """
    Generate a unique ID for a new chat session.
    """

    return str(uuid4())


# ---------------------------------------------------------
# SAVE MESSAGE
# ---------------------------------------------------------

def append_message(
    session_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Save a user or assistant message.
    """

    if not session_id:
        raise ValueError(
            "session_id cannot be empty."
        )

    if role not in {
        "user",
        "assistant",
    }:
        raise ValueError(
            "role must be 'user' or "
            "'assistant'."
        )

    message = {
        "role": role,
        "content": str(content),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "metadata": metadata or {},
    }

    if _redis_is_available():
        client = _get_redis_client()

        key = _session_key(
            session_id
        )

        client.rpush(
            key,
            json.dumps(message),
        )

        client.expire(
            key,
            REDIS_SESSION_TTL_SECONDS,
        )

        return message

    with _MEMORY_LOCK:
        if session_id not in _MEMORY_SESSIONS:
            _MEMORY_SESSIONS[session_id] = []

        _MEMORY_SESSIONS[
            session_id
        ].append(message)

    return message


# ---------------------------------------------------------
# GET SESSION HISTORY
# ---------------------------------------------------------

def get_session_history(
    session_id: str,
) -> list[dict[str, Any]]:
    """
    Return all messages belonging to one session.
    """

    if not session_id:
        return []

    if _redis_is_available():
        client = _get_redis_client()

        saved_messages = client.lrange(
            _session_key(session_id),
            0,
            -1,
        )

        history = []

        for saved_message in saved_messages:
            try:
                history.append(
                    json.loads(
                        saved_message
                    )
                )

            except json.JSONDecodeError:
                continue

        return history

    with _MEMORY_LOCK:
        return [
            message.copy()
            for message in _MEMORY_SESSIONS.get(
                session_id,
                [],
            )
        ]


# ---------------------------------------------------------
# CLEAR SESSION
# ---------------------------------------------------------

def clear_session(
    session_id: str,
) -> bool:
    """
    Delete all history for one session.
    """

    if not session_id:
        return False

    if _redis_is_available():
        client = _get_redis_client()

        deleted_count = client.delete(
            _session_key(session_id)
        )

        return deleted_count > 0

    with _MEMORY_LOCK:
        existed = (
            session_id
            in _MEMORY_SESSIONS
        )

        _MEMORY_SESSIONS.pop(
            session_id,
            None,
        )

    return existed


# ---------------------------------------------------------
# STORAGE BACKEND
# ---------------------------------------------------------

def get_storage_backend() -> str:
    """
    Return the currently active storage type.
    """

    if _redis_is_available():
        return "redis"

    return "memory"