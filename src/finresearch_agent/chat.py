from __future__ import annotations

from typing import Any


def dedupe_consecutive_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop consecutive duplicate (role, content) messages.

    If duplicates exist and a later duplicate contains a "report" while the kept
    one doesn't, keep the "report" field.
    """
    out: list[dict[str, Any]] = []
    last_key: tuple[Any, Any] | None = None
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        key = (role, content)
        if out and key == last_key:
            if "report" in msg and "report" not in out[-1]:
                out[-1]["report"] = msg["report"]
            continue
        out.append(msg)
        last_key = key
    return out


def append_message_dedup(
    messages: list[dict[str, Any]],
    *,
    role: str,
    content: str,
    report: Any | None = None,
) -> list[dict[str, Any]]:
    """Append a message unless it's identical to the last one."""
    item: dict[str, Any] = {"role": role, "content": content}
    if report is not None:
        item["report"] = report

    if messages:
        last = messages[-1]
        if isinstance(last, dict) and last.get("role") == role and last.get("content") == content:
            if "report" in item and "report" not in last:
                last["report"] = item["report"]
            if "report" not in item or last.get("report") == item.get("report"):
                return messages

    return [*messages, item]
