"""Validate the gold-set JSONL files against goldset_schema.json + real-text provenance.

Two independent checks per record:
  1. JSON Schema conformance against ``03_CORPUS/goldset_schema.json``
     (obligations -> obligation_annotation; changes -> change_annotation).
  2. Provenance: each obligation ``exact_quote`` occurs verbatim (normalized) in the
     real Aug-2024 PDF; each change ``old_text``/``new_text`` occurs in the correct PDF.

Exit non-zero if any record fails either check. This is the gate that guarantees the
gold set is schema-valid and traceable to the real corpus (no fabricated text).

Usage:
    python scripts/validate_goldset.py [--schema PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from jsonschema import Draft7Validator

AUG_PDF = "data/goldsets/circulars/stockbrokers_master_2024-08-09.pdf"
JUN_PDF = "data/goldsets/circulars/stockbrokers_master_2025-06-17.pdf"
OBLIGATIONS = "data/goldsets/obligations.jsonl"
CHANGESET = "data/goldsets/changeset.jsonl"
DEFAULT_SCHEMA = "/Users/rahul/Downloads/CircularOS-Winning-Plan/03_CORPUS/goldset_schema.json"

_SMART = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}


def prov_norm(s: str) -> str:
    for k, v in _SMART.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def load_pdf_text(path: str) -> str:
    import fitz

    doc = fitz.open(path)
    text = "\n".join(doc[i].get_text("text") for i in range(doc.page_count))
    doc.close()
    return prov_norm(text)


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def sub_validator(schema: dict, definition: str) -> Draft7Validator:
    """Build a validator for one definition, carrying the shared definitions."""
    return Draft7Validator({"$ref": f"#/definitions/{definition}",
                            "definitions": schema["definitions"]})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    args = ap.parse_args()

    if not os.path.exists(args.schema):
        print(f"ERROR: schema not found: {args.schema}")
        return 2

    with open(args.schema) as f:
        schema = json.load(f)
    obl_v = sub_validator(schema, "obligation_annotation")
    chg_v = sub_validator(schema, "change_annotation")

    obligations = load_jsonl(OBLIGATIONS)
    changes = load_jsonl(CHANGESET)
    aug = load_pdf_text(AUG_PDF)
    jun = load_pdf_text(JUN_PDF)

    errors: list[str] = []

    for r in obligations:
        for e in obl_v.iter_errors(r):
            errors.append(f"[schema] {r.get('id')}: {e.message}")
        q = prov_norm(r["source"]["exact_quote"])
        if q not in aug:
            errors.append(f"[provenance] {r.get('id')}: quote not in Aug-2024")

    for r in changes:
        for e in chg_v.iter_errors(r):
            errors.append(f"[schema] {r.get('id')}: {e.message}")
        if r.get("old_text") and prov_norm(r["old_text"]) not in aug:
            errors.append(f"[provenance] {r.get('id')}: old_text not in Aug-2024")
        if r.get("new_text") and prov_norm(r["new_text"]) not in jun:
            errors.append(f"[provenance] {r.get('id')}: new_text not in Jun-2025")

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):")
        for e in errors[:40]:
            print("  -", e)
        return 1

    print(f"VALID: {len(obligations)} obligations + {len(changes)} changes")
    print("  - all conform to goldset_schema.json (draft-07)")
    print("  - all obligation quotes occur verbatim in the Aug-2024 PDF")
    print("  - all change old_text/new_text occur in the correct PDF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
