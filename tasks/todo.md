# Task: Phase 1 — Real Corpus + The Gold Set (credibility foundation)

## Goal
Load the real SEBI stockbroker master circular PAIR (Aug-2024 → Jun-2025) and build the
hand-annotated gold set (~120–150 obligations) + labeled change-set (~20–30 changes + ~10
cosmetic non-changes), grounded entirely in real PDF text. Load into the eval tables.

Phase 0 (end-to-end wiring) is DONE — see git history. This phase adds real data + ground truth.

## Steps
- [ ] 1. Acquire Jun-2025 PDF from sebi.gov.in (Aug-2024 already present at data/corpus/).
      Move/copy both to data/goldsets/circulars/ with canonical names. Record provenance
      (URL, ref no., date, SHA-256, download date) in data/goldsets/PROVENANCE.md.
- [ ] 2. Ingest BOTH through the real parser → clauses in DB. Confirm Aug-2024 ≥100 clauses.
      Extract full text of both to working files for annotation + validation.
- [ ] 3. Run extraction graph on Aug-2024 (bounded slice, rate-limit aware) → target ≥100
      obligations. Report the REAL count honestly whatever it is.
- [ ] 4. Build gold set: ~120–150 obligation annotations from REAL Aug-2024 clause text.
      Composition: ~50% straightforward, ~25% conditional/exception, ~15% multi-actor/xref,
      ~10% negative (definitions/informational). Tag difficulty easy/medium/hard.
      Export data/goldsets/obligations.jsonl (conforms to goldset_schema.json).
      AI-first-pass; mark UNVERIFIED pending human review (I am not a human verifier).
- [ ] 5. Build labeled change-set: ≥20–30 real CREATED/MODIFIED/REMOVED changes confirmed
      against BOTH PDFs (DDPI-replaces-PoA, QSB enhanced monitoring, tightened timeline, etc.)
      + ~10 cosmetic renumberings labeled NOT_A_CHANGE. Export data/goldsets/changeset.jsonl.
- [ ] 6. Validator: every obligation exact_quote must appear verbatim in Aug-2024 real text;
      every change old_text in Aug-2024, new_text in Jun-2025. Fail loud on any miss.
      This is the anti-fabrication guard.
- [ ] 7. Loader packages/evaluation/datasets.py — idempotent load of both JSONL into
      EvaluationDataset + EvaluationExample. Re-run = no duplicates.
- [ ] 8. Provenance + honesty doc data/goldsets/README.md (size, composition, difficulty
      breakdown, how built, verification status stated honestly).

## Risks / open questions
- Jun-2025 PDF: must find the real attachdocs URL behind the SEBI landing HTML page.
- LLM quota: Gemini 2.5-flash free tier + Groq 30 RPM/1K RPD. Extraction on the full 419pp
  is thousands of calls — infeasible + rate-limited. Run on a bounded obligation-dense slice
  sufficient to clear ≥100 obligations; report real number, do not fabricate.
- Human verification is MANDATORY per spec but I am an AI. I build a rigorous first pass
  grounded in real quotes + a substring validator against the real PDF, and mark the set
  UNVERIFIED-pending-human-review honestly. Will flag to user.
- Parser clause reconstruction is heading-based; annotation spans should reference real text.

## Done criteria (exit gate)
- [ ] Both real PDFs in data/goldsets/circulars/ with provenance incl. SHA-256.
- [ ] Aug-2024 ingests ≥100 clauses; extraction graph produces ≥100 obligations on it.
- [ ] obligations.jsonl validates vs schema, ~120–150 records incl. negatives + hard cases,
      loaded into eval tables.
- [ ] changeset.jsonl validates, includes ≥3 recognizable real changes + cosmetic non-changes.
- [ ] Loader idempotent; eval tables show loaded counts.
- [ ] README documents size/composition/verification honestly.
- [ ] Written report with real numbers.

## Review (Phase 1)

**Done & verified:**
- Corpus: both real PDFs in `data/goldsets/circulars/` (Aug-2024 419pp sha a6a30dd4…,
  Jun-2025 399pp sha 6ffd3e9f…). Jun-2025 downloaded from sebi.gov.in; both first pages
  confirm ref numbers/dates; Jun explicitly supersedes Aug. Provenance in PROVENANCE.md.
- Ingest: both ingested through the real parser → DB. Aug-2024 = **1,214 clauses** (≥100 ✓),
  Jun-2025 = 702 clauses. Fixed a real parser bug (PyMuPDF lone surrogates rejected by
  Postgres) — now stripped at parse time in parser.py.
- Gold set: `data/goldsets/obligations.jsonl` = **123 records** (108 positive / 15 negative
  = 12%), difficulty 29/72/22 easy/med/hard, tags conditional 33 · multi-actor 23 ·
  cross-reference 19 · implicit-deadline 6 · definition 7. Validates vs goldset_schema.json
  AND every exact_quote proven verbatim in the real Aug-2024 PDF.
- Change-set: `data/goldsets/changeset.jsonl` = 19 records (6 CREATED · 1 MODIFIED · 12
  NOT_A_CHANGE). old_text proven in Aug, new_text in Jun. Honest finding: the pair is mostly
  a re-consolidation; DDPI-replaces-PoA and QSB "enhanced monitoring" PREDATE this pair
  (present + identical in both) → recorded as NOT_A_CHANGE with notes, not fabricated.
- Loader: `packages/evaluation/datasets.py` idempotent — DB shows 123 + 19 examples after
  two loads (not doubled); example_count matches actual.
- README.md documents size/composition/verification honestly (AI-first-pass, human
  verification PENDING — I am not a human verifier; text is machine-proven, labels aren't).
- Gates: py_compile + imports clean; new files ruff-clean under project config; jsonschema
  added to dev deps.

**Extraction (≥100 obligations gate): PASSED — 106 obligations, 374 citations** on Aug-2024
(120 cue-ranked clauses, 89,833 real tokens, 2 transient errors). ExtractionRun COMPLETED.
  - Env caveat (NOT code): `.env` reasoning model `gemini-2.5-flash` now returns 404
    (Google deprecated it for new keys); Groq's free 200K-tokens/day cap was exhausted by
    the classification pass. Ran successfully by routing fast+reasoning to `gemini-flash-latest`
    (the 10-key Gemini pool in .env gives 10x quota) via env override.
  - ACTION FOR USER: update `.env` FAST_MODEL_NAME / REASONING_MODEL_NAME to
    `gemini-flash-latest` (or attach Groq billing) before the Phase-4 eval + demo.

**Not mine (pre-existing uncommitted):** .env.example, apps/api/config.py,
packages/ai/providers.py were already modified at session start (Phase 0).

## No commits. Leave working tree dirty for review.
