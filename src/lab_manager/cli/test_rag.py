#!/usr/bin/env python3
"""Test the RAG Q&A service with example queries.

Usage:
    uv run python scripts/test_rag.py
    uv run python scripts/test_rag.py --api   # test via HTTP API instead of direct call
"""

from __future__ import annotations

import argparse
import json
import time

EXAMPLE_QUERIES = [
    "Do we have any items from Thermo Fisher?",
    "What orders were received this month?",
    "Show me all lot numbers for catalog number A1895",
    "What's expiring soon?",
    "Who received the most orders?",
    "我们有多少供应商?",
]


def test_direct():
    """Test via direct Python call to rag.ask()."""
    from lab_manager.database import get_session_factory
    from lab_manager.services.rag import ask

    factory = get_session_factory()
    session = factory()

    try:
        for i, question in enumerate(EXAMPLE_QUERIES, 1):
            print(f"\n{'=' * 70}")
            print(f"[{i}/{len(EXAMPLE_QUERIES)}] {question}")
            print("=" * 70)

            start = time.time()
            result = ask(question, session)
            elapsed = time.time() - start

            print(f"Source:  {result['source']}")
            print(f"Rows:    {len(result['raw_results'])}")
            print(f"Time:    {elapsed:.1f}s")
            print(f"Answer:  {result['answer']}")

            if result["raw_results"]:
                print(
                    f"Sample:  {json.dumps(result['raw_results'][:3], default=str, ensure_ascii=False)}"
                )

            print()
    finally:
        session.close()


def test_api():
    """Test via HTTP API calls."""
    import urllib.request
    import urllib.parse

    base_url = "http://localhost:8000/api/v1/ask"

    for i, question in enumerate(EXAMPLE_QUERIES, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(EXAMPLE_QUERIES)}] {question}")
        print("=" * 70)

        # Test POST
        start = time.time()
        data = json.dumps({"question": question}).encode("utf-8")
        req = urllib.request.Request(
            base_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
                result = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"ERROR (POST): {e}")
            continue

        elapsed = time.time() - start

        print(f"Source:  {result['source']}")
        print(f"Rows:    {len(result['raw_results'])}")
        print(f"Time:    {elapsed:.1f}s")
        print(f"Answer:  {result['answer']}")

        if result["raw_results"]:
            print(
                f"Sample:  {json.dumps(result['raw_results'][:3], default=str, ensure_ascii=False)}"
            )

        print()

    # Also test GET endpoint with one query
    print(f"\n{'=' * 70}")
    print("Testing GET endpoint...")
    print("=" * 70)
    q = urllib.parse.quote("How many products do we have?")
    req = urllib.request.Request(f"{base_url}?q={q}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            result = json.loads(resp.read().decode("utf-8"))
        print(f"GET /api/v1/ask?q=... -> {result['answer']}")
    except Exception as e:
        print(f"ERROR (GET): {e}")


def main():
    parser = argparse.ArgumentParser(description="Test RAG Q&A service")
    parser.add_argument(
        "--api",
        action="store_true",
        help="Test via HTTP API (requires running server)",
    )
    args = parser.parse_args()

    if args.api:
        test_api()
    else:
        test_direct()


if __name__ == "__main__":
    main()
