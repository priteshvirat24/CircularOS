"""Same-model and same-batch guards for full-corpus extraction."""

from __future__ import annotations

import uuid

import pytest

from packages.regulatory_core.models.agents import ExtractionRun, WorkflowStatus
from scripts.extract_obligations_full import (
    SourceSection,
    _as_json_list,
    _checkpoint,
    _chunk_section,
    _load_sections,
    _optional_text,
    _run_config,
    assert_consistent_run_provenance,
)


def _run(
    *,
    provider: str = "mistral",
    model: str = "mistral-large-latest",
    corpus_run_id: str = "corpus-1",
    config_hash: str = "config-1",
) -> ExtractionRun:
    return ExtractionRun(
        document_id=uuid.uuid4(),
        workflow_type="full_section",
        status=WorkflowStatus.RUNNING,
        checkpoint_data={
            "version": 2,
            "provider": provider,
            "model": model,
            "corpus_run_id": corpus_run_id,
            "run_config_hash": config_hash,
            "run_config": {},
            "sections": {},
            "errors": [],
        },
    )


def test_phase45_run_config_is_auditable_and_contains_no_secret() -> None:
    config = _run_config()

    assert config["provider"] == "mistral"
    assert config["model"] == "mistral-large-latest"
    assert config["concurrency"] == 4
    assert config["request_start_interval_seconds"] >= 15.0
    assert config["chunking_version"] == "line-boundary-nonoverlap-v1"
    assert config["section_locator_version"] == "toc-title-aligned-body-region-v4"
    assert "the fifth" in config["rate_limit_source"]
    assert "four-requests/minute" in config["rate_limit_source"]
    assert "api_key" not in config
    assert len(config["hash"]) == 64


def test_section_chunking_is_nonoverlapping_bounded_and_lossless() -> None:
    body = "alpha line\n" * 7 + "omega"
    section = SourceSection(3, "Registration", body, 100, 100 + len(body))

    chunks = _chunk_section(section, max_chars=25)

    assert "".join(chunk.body for chunk in chunks) == body
    assert all(len(chunk.body) <= 25 for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.chunk_count == len(chunks) for chunk in chunks)
    assert chunks[0].char_start == 100
    assert chunks[-1].char_end == 100 + len(body)
    assert all(
        left.char_end == right.char_start for left, right in zip(chunks, chunks[1:], strict=False)
    )


def test_registry_boundary_normalizes_null_sentinels_and_string_limits() -> None:
    assert _as_json_list("null") is None
    assert _as_json_list(["actual condition", "N/A", "none"]) == ["actual condition"]
    assert _optional_text(" not specified ") is None
    assert _optional_text("quarterly", max_length=100) == "quarterly"
    assert _optional_text("x" * 103, max_length=100) == "x" * 100


@pytest.mark.parametrize(
    "title",
    (
        "stockbrokers_master_2024-08-09.pdf",
        "stockbrokers_master_2025-06-17.pdf",
    ),
)
def test_real_top_level_sections_are_all_located_in_monotonic_body_order(
    title: str,
) -> None:
    sections = _load_sections(title)
    starts = [section.char_start for section in sections]

    assert len(sections) in {94, 98}
    assert all(section.body.strip() for section in sections)
    assert all(start is not None and start > 16_000 for start in starts)
    assert starts == sorted(starts)


def test_consistency_guard_accepts_one_shared_corpus_config() -> None:
    provenance = assert_consistent_run_provenance([_run(), _run()])

    assert provenance == {
        "corpus_run_id": "corpus-1",
        "run_config_hash": "config-1",
        "provider": "mistral",
        "model": "mistral-large-latest",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("provider", "gemini"),
        ("model", "gemini-flash-latest"),
        ("corpus_run_id", "corpus-2"),
        ("config_hash", "config-2"),
    ),
)
def test_consistency_guard_rejects_mixed_corpus(field: str, value: str) -> None:
    changed = {field: value}

    with pytest.raises(RuntimeError, match="Mixed or missing full-corpus provenance"):
        assert_consistent_run_provenance([_run(), _run(**changed)])


def test_legacy_gemini_checkpoint_is_not_relabelled_as_mistral() -> None:
    legacy = ExtractionRun(
        document_id=uuid.uuid4(),
        workflow_type="full_section",
        status=WorkflowStatus.PAUSED,
        checkpoint_data={"version": 1, "model": "gemini-flash-latest", "sections": {}},
    )

    checkpoint = _checkpoint(legacy)
    assert checkpoint["model"] == "gemini-flash-latest"
    assert checkpoint["provider"] is None
    assert checkpoint["run_config_hash"] is None
