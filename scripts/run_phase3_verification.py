#!/usr/bin/env python3
"""Run the free-tier Phase-3 verification loop over the partial August corpus."""

from __future__ import annotations

import asyncio
import json

from apps.api.services.verification_service import run_document_verification


async def main() -> None:
    summary = await run_document_verification(
        "stockbrokers_master_2024-08-09.pdf", free_tier_cooldown_seconds=12.0
    )
    print(json.dumps(summary.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
