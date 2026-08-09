#!/usr/bin/env python3
"""Persist one real deterministic blast-radius assessment."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

from apps.api.services.impact_service import persist_latest_change_impacts


async def main() -> None:
    results = await persist_latest_change_impacts()
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
