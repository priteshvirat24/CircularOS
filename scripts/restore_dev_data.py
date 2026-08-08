"""Restore the dev DB's real-corpus state: ingest both circular PDFs + reload the gold sets.

Parse-only and deterministic — NO LLM calls. Restores ``regulatory_documents`` + pages +
clauses for the Aug-2024 and Jun-2025 stockbroker master circulars (enough for the diff engine,
which reads page text), then reloads the obligation/change gold sets.

Needed because ``tests/conftest.py`` truncates ``organizations ... CASCADE``, which cascades
through ``regulatory_documents`` and wipes the ingested corpus whenever the pytest suite runs
against the shared dev database. Run this after a test run to repopulate.

    python scripts/restore_dev_data.py
"""

from __future__ import annotations

import asyncio
import os

from packages.evaluation.datasets import load_goldsets
from scripts.smoke_extraction import ingest_pdf

CIRCULARS = [
    "data/goldsets/circulars/stockbrokers_master_2024-08-09.pdf",
    "data/goldsets/circulars/stockbrokers_master_2025-06-17.pdf",
]


async def main() -> int:
    for path in CIRCULARS:
        if not os.path.exists(path):
            print(f"ERROR: missing corpus PDF {path}")
            return 2
        print(f"[ingest] {path}")
        doc_id = await ingest_pdf(path, max_clauses=None)
        print(f"         document_id={doc_id}")

    print("[goldset] reloading obligation + change datasets ...")
    result = await load_goldsets()
    print(f"          {result}")
    print("RESTORE COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
