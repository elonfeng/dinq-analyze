"""
Stream Protocol Utilities

This module provides utilities for handling streaming responses and message
formatting. It keeps backward-compatible helpers used across the codebase and
adds a unified event schema that all streaming APIs can adopt gradually.
"""

import json
from enum import Enum
from typing import Any, Dict, Optional


class MessageType(Enum):
    """Legacy message types used by the Scholar streaming API."""

    STATUS = "status"
    THINK_TITLE = "thinkTitle"
    THINK_CONTENT = "thinkContent"
    COMMAND = "command"
    FINAL_CONTENT = "finalContent"
    ERROR = "error"


class Command(Enum):
    """Legacy command types that can be sent to the client."""

    OPEN_BROWSER = "openBrowser"
    SHOW_VISUALIZATION = "showVisualization"


def format_stream_message(message: Dict[str, Any]) -> str:
    """
    Format a message for streaming using Server-Sent Events (SSE) protocol.

    Args:
        message: The message to format.

    Returns:
        Formatted message string for SSE.
    """

    return f"data: {json.dumps(message, ensure_ascii=False)}\n\n"


def create_message(type_: MessageType, content: str) -> Dict[str, Any]:
    """
    Create a legacy message with the specified type and content.

    Args:
        type_: The legacy type of message.
        content: The textual content of the message.

    Returns:
        A dictionary representing the message.
    """

    return {
        "type": type_.value,
        "content": content,
    }


def create_status(content: str) -> Dict[str, Any]:
    """Create a status message (legacy + unified metadata)."""

    msg = create_message(MessageType.STATUS, content)
    msg.setdefault("source", "scholar")
    msg.setdefault("event_type", "progress")
    msg.setdefault("message", content)
    return msg


def create_think_title(content: str) -> Dict[str, Any]:
    """Create a thinking title message (legacy + unified metadata)."""

    msg = create_message(MessageType.THINK_TITLE, content)
    msg.setdefault("source", "scholar")
    msg.setdefault("event_type", "progress")
    msg.setdefault("message", content)
    return msg


def create_think_content(content: str) -> Dict[str, Any]:
    """Create a thinking content message (legacy + unified metadata)."""

    msg = create_message(MessageType.THINK_CONTENT, content)
    msg.setdefault("source", "scholar")
    msg.setdefault("event_type", "progress")
    msg.setdefault("message", content)
    return msg


def create_command(
    command: Command,
    description: str,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a command message.

    Args:
        command: The command type.
        description: Description of the command.
        target: Optional target for the command (e.g., URL).

    Returns:
        A dictionary representing the command message.
    """

    command_data: Dict[str, Any] = {
        "action": command.value,
        "description": description,
    }

    if target:
        command_data["target"] = target

    return {
        "type": MessageType.COMMAND.value,
        "content": command_data,
        "source": "scholar",
        "event_type": "command",
        "message": description,
        "payload": command_data,
    }


def create_final_content(content: str) -> Dict[str, Any]:
    """Create a final content message (legacy + unified metadata)."""

    msg = create_message(MessageType.FINAL_CONTENT, content)
    msg.setdefault("source", "scholar")
    msg.setdefault("event_type", "final")
    msg.setdefault("message", content)
    return msg


def create_error(content: str) -> Dict[str, Any]:
    """Create an error message (legacy + unified metadata)."""

    msg = create_message(MessageType.ERROR, content)
    msg.setdefault("source", "scholar")
    msg.setdefault("event_type", "error")
    msg.setdefault("message", content)
    return msg


# === Unified streaming helpers =================================================

def create_event(
    *,
    source: str,
    event_type: str,
    message: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    step: Optional[str] = None,
    progress: Optional[float] = None,
    legacy_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a unified streaming event dictionary.

    This helper is intended to be used by all streaming APIs (scholar, github,
    linkedin, etc.) so that the frontend can rely on a consistent schema:

    {
        "source": "scholar" | "github" | "linkedin",
        "event_type": "start" | "progress" | "data" | "final" | "error" | "end",
        "step": "...",                # optional logical step name
        "message": "...",             # human readable text
        "progress": 0-100,            # optional percentage
        "payload": {...},             # optional structured data
        "type": "...",                # optional legacy type for backward compat
    }
    """

    event: Dict[str, Any] = {
        "source": source,
        "event_type": event_type,
    }

    if legacy_type is not None:
        event["type"] = legacy_type

    if message is not None:
        event["message"] = message

    if step is not None:
        event["step"] = step

    if progress is not None:
        event["progress"] = progress

    if payload is not None:
        event["payload"] = payload

    return event


def sse_event(
    *,
    source: str,
    event_type: str,
    message: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    step: Optional[str] = None,
    progress: Optional[float] = None,
    legacy_type: Optional[str] = None,
) -> str:
    """
    Convenience helper: build a unified event and format it as SSE line(s).
    """

    event = create_event(
        source=source,
        event_type=event_type,
        message=message,
        payload=payload,
        step=step,
        progress=progress,
        legacy_type=legacy_type,
    )
    return format_stream_message(event)


def create_error_payload(
    *,
    code: str,
    message: str,
    retryable: bool = False,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a unified error payload used by all streaming endpoints.

    Schema:
    {
        "code": "...",
        "message": "...",
        "retryable": true|false,
        "detail": {...} | null
    }
    """

    payload: Dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": bool(retryable),
        "detail": detail,
    }
    return payload


def create_error_event(
    *,
    source: str,
    code: str,
    message: str,
    retryable: bool = False,
    detail: Optional[Dict[str, Any]] = None,
    step: Optional[str] = None,
    legacy_type: str = MessageType.ERROR.value,
) -> Dict[str, Any]:
    """
    Create a unified error event, with backward-compatible legacy fields.
    """

    payload = create_error_payload(code=code, message=message, retryable=retryable, detail=detail)
    event = create_event(
        source=source,
        event_type="error",
        message=message,
        payload=payload,
        step=step,
        legacy_type=legacy_type,
    )
    # Some legacy clients expect `content` for errors.
    event.setdefault("content", message)
    # Some callers previously used {"error": "..."} in SSE payloads.
    event.setdefault("error", message)
    return event
