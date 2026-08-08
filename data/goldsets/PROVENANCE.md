# CORPUS PROVENANCE

Provenance record for the SEBI regulatory documents CircularOS runs against. Every obligation,
diff, and eval number traces back to one of these files. Provenance is itself a credibility
signal: a regulator trusts a system that tracks where its documents came from.

All documents are public regulatory circulars hosted on **sebi.gov.in**.

## Primary demo pair — Master Circular for Stock Brokers (version chain)

The Jun-2025 master circular **supersedes** the Aug-2024 one and incorporates all directions up
to Jun 10, 2025. That makes the two documents the same document at two points in time — the ideal
input for the diff engine.

### OLD (v1) — `stockbrokers_master_2024-08-09.pdf`

| Field | Value |
|---|---|
| Title | Master Circular for Stock Brokers |
| Reference No. | `SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2024/110` |
| Date | August 09, 2024 |
| Supersedes | Master Circular for Stock Brokers dated May 22, 2024 |
| Landing page | https://www.sebi.gov.in/legal/master-circulars/aug-2024/master-circular-for-stock-brokers_85605.html |
| Pages | 419 |
| Size | 5,428,779 bytes |
| SHA-256 | `a6a30dd46ec3230348400e38b50707cb2aa2634de07a48ea02602cdb76a55822` |
| Download date | 2026-08-07 (acquired during Phase 0; re-filed into goldsets in Phase 1) |

### NEW (v2) — `stockbrokers_master_2025-06-17.pdf`

| Field | Value |
|---|---|
| Title | Master Circular for Stock Brokers |
| Reference No. | `SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/90` |
| Date | June 17, 2025 (effective Jun 10, 2025) |
| Supersedes | Master Circular for Stock Brokers dated August 09, 2024 |
| Landing page | https://www.sebi.gov.in/legal/master-circulars/jun-2025/master-circular-for-stock-brokers_94623.html |
| Direct PDF | https://www.sebi.gov.in/sebi_data/attachdocs/jun-2025/1750158789381.pdf |
| Pages | 399 |
| Size | 4,728,824 bytes |
| SHA-256 | `6ffd3e9fe5a486594e942ed187d7ecf117f13ea64fcd19fb13920697a5af7880` |
| Download date | 2026-08-07 |

Both documents' first pages were read and confirmed to carry the reference numbers and dates
above, and the Jun-2025 circular's opening paragraph explicitly states it supersedes the
Aug-2024 circular — confirming the version relationship is official, not constructed.

## Integrity verification

SHA-256 is recomputable at any time with:

```bash
shasum -a 256 data/goldsets/circulars/*.pdf
```

The values above must match. The repo's `packages/document_processing/integrity.py`-style check
(`content[:5] == b"%PDF-"` + SHA-256) is applied at ingest.

## Notes

- The original Phase-0 working copy of the Aug-2024 circular lives at
  `data/corpus/sebi_stockbrokers_master_aug2024.pdf` (identical bytes / same SHA-256). The
  canonical Phase-1 copy under `data/goldsets/circulars/` is the one the gold set and diff run
  against.
- A second intermediary corpus (Master Circular for Investment Advisers), suggested in
  `03_CORPUS/CORPUS_SELECTION.md` for the SupTech scalability proof, is **not** acquired in
  Phase 1 — it is only needed for Phase 5/7 and is out of scope here.
