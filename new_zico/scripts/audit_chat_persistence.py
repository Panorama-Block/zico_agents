#!/usr/bin/env python3
"""Audit and optionally remove safe ghost chat conversations.

A historical bug leaked the Panorama gateway composite resource identifier
(`<userId>:<conversationId>`) into the public chat API. Reading one of those
IDs could then create a second conversation whose *domain* conversationId was
that composite value.

This script is deliberately safe-by-default. It only deletes a suspicious row
when --apply-safe is supplied AND the row contains no user messages. Rows with
user content are reported for manual reconciliation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.service.chat_persistence_store import ChatPersistenceStore

DISCLAIMER_PREFIX = "This highly experimental chatbot is not intended"


def canonical_target(user_id: str, conversation_id: str) -> Optional[str]:
    """Return the canonical conversation-* suffix for a composite ghost ID."""
    decoded = unquote(conversation_id)
    prefixes = (
        f"{user_id}:",
        f"{quote(user_id, safe='')}:",
        f"{unquote(user_id)}:",
    )
    for candidate in {conversation_id, decoded}:
        for prefix in prefixes:
            if candidate.startswith(prefix):
                suffix = unquote(candidate[len(prefix):])
                if suffix.startswith("conversation-"):
                    return suffix
    return None


def meaningful_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        message
        for message in messages
        if message.get("role") == "user"
        or not str(message.get("content") or "").startswith(DISCLAIMER_PREFIX)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument(
        "--apply-safe",
        action="store_true",
        help="Delete only ghost rows with zero meaningful/user messages.",
    )
    args = parser.parse_args()

    store = ChatPersistenceStore()
    result = store._client.list(
        "conversations",
        {
            "where": {"userId": args.user_id},
            "orderBy": {"createdAt": "asc"},
        },
    )
    rows = result.get("data", []) if isinstance(result, dict) else []
    canonical_ids = {
        row.get("conversationId")
        for row in rows
        if isinstance(row, dict) and str(row.get("conversationId") or "").startswith("conversation-")
    }

    report: List[Dict[str, Any]] = []
    deleted = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        conversation_id = str(row.get("conversationId") or "")
        target = canonical_target(args.user_id, conversation_id)
        if not target:
            continue

        messages = store.list_messages(args.user_id, conversation_id)
        meaningful = meaningful_messages(messages)
        item = {
            "ghost_conversation_id": conversation_id,
            "canonical_target": target,
            "canonical_exists": target in canonical_ids,
            "title": row.get("title"),
            "message_count": row.get("messageCount"),
            "meaningful_message_count": len(meaningful),
            "safe_to_delete": len(meaningful) == 0,
            "action": "report_only",
        }

        if args.apply_safe and len(meaningful) == 0:
            deleted_ok = store.delete_conversation(args.user_id, conversation_id)
            item["action"] = "deleted" if deleted_ok else "already_missing"
            if deleted_ok:
                deleted += 1
        elif meaningful:
            item["action"] = "manual_reconciliation_required"

        report.append(item)

    print(json.dumps({"deleted": deleted, "ghosts": report}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
