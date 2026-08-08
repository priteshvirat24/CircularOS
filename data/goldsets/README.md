# CircularOS Gold Set — How This Benchmark Was Built

This directory holds the hand-annotated ground truth CircularOS measures itself against.
It is the credibility spine of the submission: the extraction and diff numbers reported
in later phases are computed against **these** files, not invented.

Everything here traces to two real, public SEBI documents (see `PROVENANCE.md`):

| Role | File | Ref | Date | Pages | SHA-256 (short) |
|---|---|---|---|---|---|
| OLD | `circulars/stockbrokers_master_2024-08-09.pdf` | SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2024/110 | Aug 09, 2024 | 419 | `a6a30dd4…` |
| NEW | `circulars/stockbrokers_master_2025-06-17.pdf` | SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/90 | Jun 17, 2025 | 399 | `6ffd3e9f…` |

## Files

- **`obligations.jsonl`** — 123 obligation annotations from the Aug-2024 circular
  (conforms to `03_CORPUS/goldset_schema.json`).
- **`changeset.jsonl`** — 19 labeled changes / non-changes between the two circulars.
- **`PROVENANCE.md`** — URLs, reference numbers, dates, SHA-256, download date.

## Obligation gold set — size & composition (`obligations.jsonl`)

- **123 records total** — 108 positive obligations, **15 negative examples (12%)**.
  The negatives are definitional/informational clauses (e.g. the definition of
  "margins", the definition of "technical glitch", the description of a Power of
  Attorney) that must **not** yield an obligation — they test extraction *precision*.
- **Difficulty:** 29 easy · 72 medium · 22 hard (`difficulty` field per record).
- **Hard-case tags** (a record can carry several):
  - `conditional` — 33 (e.g. "unless otherwise agreed…", "if a dispute arises…")
  - `multi-actor` — 23 (broker / TM / CM / exchange / depository / clearing corp)
  - `cross-reference` — 19 ("as per para X", "in accordance with the Regulations")
  - `implicit-deadline` — 6 (deadlines expressed by reference, e.g. "the arbitration period")
  - `definition` — 7, `informational` — 8, `negative` — 15
- **Coverage** spans the demo-critical sections: QSB (§18), client dealings & running
  account (§22, §47), PoA/DDPI (§35–36), margin collection/pledge (§39–42), unauthorised
  trading (§34), cyber (§61), authorised persons (§32–33), Smart Order Routing (§57),
  registration/supervision (§1–17), and misc record-keeping/grievance (§72–93).

Each record carries: the **verbatim `exact_quote`** from the PDF, its `clause_ref`, the
`normalized_obligation`, structured fields (`actor`, `action`, `object`, `conditions`,
`exceptions`, `frequency`, `deadline`, `evidence_requirement`, `penalty_reference`),
`difficulty`, `tags`, and `annotator_notes` for judgment calls.

## Change-set — composition (`changeset.jsonl`)

19 records: **6 CREATED · 1 MODIFIED · 12 NOT_A_CHANGE** (cosmetic renumberings).

The Jun-2025 circular is, overwhelmingly, a **re-consolidation** of the Aug-2024 one:
it inserts a small number of genuinely new sections and then renumbers everything after
them. Our change-set reflects that honestly:

- **CREATED (genuinely new in Jun-2025, verified absent in Aug-2024):**
  - §17 *Framework for Monitoring and Supervision of System Audit through Technology
    based Measures* (+ two of its new sub-obligations: exchanges build a web portal
    monitoring the audit lifecycle; capture auditor geo-location for physical-visit proof)
  - §71 GIFT-IFSC Separate Business Unit facilitation
  - §72 NDS-OM access for Government Securities via an SBU
  - §88 Association of Board-regulated persons and their agents with certain persons
- **MODIFIED (verified textual change):** the section title *"Review of norms relating to
  trading by Members/ Sub-Brokers"* → *"…by Members"* (Sub-Brokers reference dropped; LOW).
- **NOT_A_CHANGE (cosmetic renumberings):** 12 sections whose title and substance are
  identical but whose number shifted by +1 because §17 was inserted (e.g. QSB 18→19,
  PoA 35→36, DDPI 36→37, margins 39→40, running account 47→48). These are the
  false-positive traps the diff engine must **not** flag as substantive.

### Honest findings (changes we dropped, and why)

`CORPUS_SELECTION.md` suggested two headline changes to look for. On close reading of the
actual PDFs, **neither is a delta between this specific pair** — both predate Aug-2024:

- **"DDPI replaces Power of Attorney"** — both the PoA section and the DDPI section exist,
  substantively identical, in **both** circulars (the DDPI mechanism was introduced by a
  2022 circular already consolidated into Aug-2024). It is a *renumbering* here, not a
  change. Recorded as `NOT_A_CHANGE`, with a note.
- **"Enhanced monitoring for QSBs"** — the QSB framework (§18→§19), including its annual
  reports, half-yearly risk review, and enhanced-monitoring paras, is present and
  unchanged in both. Likewise the cyber obligations (6-hour incident reporting, annual
  VAPT) exist in both. Not deltas for this pair.

We deliberately did **not** fabricate these into the change-set. Realness is the point:
a change that isn't in the PDF would collapse under a compliance juror's click.

## How it was built

1. Both PDFs acquired from sebi.gov.in and integrity-recorded (SHA-256) in `PROVENANCE.md`.
2. Both ingested through the real `packages/document_processing` parser into the DB
   (Aug-2024 → 1,214 clauses; Jun-2025 → 702 clauses). A parser fix was needed for the
   real document: PyMuPDF emits lone Unicode surrogates for a few glyphs, which
   PostgreSQL rejects — now stripped at parse time.
3. Candidate spans were harvested **programmatically from the real PDF text** and
   annotated. Because each `exact_quote` is a real span, the build step can and does
   **prove** provenance (below).
4. The change-set was derived by structural TOC alignment + numbering-agnostic
   section-body diffs between the two documents, with every candidate change verified
   against the PDF text before inclusion.

### Reproduce / re-validate

```bash
python scripts/build_goldset.py       # regenerate the two JSONL from the authored source
python scripts/validate_goldset.py    # schema + provenance check (must pass)
python -m packages.evaluation.datasets  # (idempotent) load into the eval tables
```

`scripts/build_goldset.py` and `scripts/validate_goldset.py` **fail loudly** if any
`exact_quote` / `old_text` / `new_text` is not found verbatim (whitespace- and
smart-punctuation-normalized) in the corresponding real PDF. A gold record therefore
cannot reference text that isn't in the source documents — this is the anti-fabrication
guarantee.

## Verification status — read this honestly

The annotation spec (`03_CORPUS/GOLDSET_ANNOTATION_SPEC.md`) mandates **human
verification** of every gold record. That step has **not** happened yet.

- These annotations are a rigorous **AI first pass**. The **text** each record points to
  is machine-verified to exist verbatim in the real Aug-2024 / Jun-2025 PDFs. The
  **structured labels** (is_obligation, actor, difficulty, materiality, …) are the
  first-pass annotator's reading and **still need a human to confirm** before any headline
  precision/recall/F1 number is published.
- The dataset `metadata_json` in the eval tables records
  `"verification_status": "AI-first-pass; human verification pending"`.
- Do not quote an F1 "against a human-verified gold set" until a human has reviewed
  `obligations.jsonl` and `changeset.jsonl`. Until then it is an AI-drafted set on real,
  provenance-checked regulatory text — already far more grounded than a mock, but not yet
  the human ground truth the pitch sentence claims.
