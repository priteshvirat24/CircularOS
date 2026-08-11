"""SupTech seed, API, authorization, and aggregate-only privacy tests."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import func, select
from starlette.testclient import TestClient

from apps.api.database import async_session_maker
from apps.api.services import create_access_token
from packages.regulatory_core.models.auth import Organization, User, UserRole
from packages.regulatory_core.models.compliance import Control, EvidenceStatus
from packages.regulatory_core.models.documents import (
    Clause,
    DocumentStatus,
    DocumentType,
    RegulatoryDocument,
)
from packages.regulatory_core.models.obligations import (
    ChangeType,
    DiffRun,
    DiffRunStatus,
    MaterialityLevel,
    Obligation,
    RegulatoryChange,
    RiskLevel,
)
from scripts.build_tenant_a_controls import (
    CONTROL_CATALOG,
    build_tenant_a_layer,
    calculate_freshness,
    plan_control_freshness,
)
from scripts.seed_suptech import seed_suptech


@dataclass(frozen=True)
class SupTechFixture:
    token: str
    circular_id: uuid.UUID
    private_document_id: uuid.UUID
    private_control_id: uuid.UUID


_CONTROL_OBLIGATION_COUNTS = (3, 3, 1, 1, 1, 2, 1, 4, 2, 2, 3, 3, 3, 2, 2)


async def _count_seed_rows() -> tuple[int, ...]:
    async with async_session_maker() as db:
        queries = (
            select(func.count(Organization.id)).where(
                Organization.slug.in_(
                    (
                        "sebi-supervisory-mirror",
                        "suptech-tenant-b-seeded",
                        "suptech-tenant-c-seeded",
                    )
                )
            ),
            select(func.count(Control.id)).where(Control.control_type == "suptech_seed"),
        )
        counts = []
        for query in queries:
            counts.append(int((await db.execute(query)).scalar_one()))
        return tuple(counts)


async def _prepare_suptech_fixture() -> SupTechFixture:
    async with async_session_maker() as db:
        real = Organization(
            name="Tenant A — Real Registry",
            slug=f"phase5-real-{uuid.uuid4()}",
            entity_type="stock_broker",
        )
        db.add(real)
        await db.flush()
        registry = RegulatoryDocument(
            title="Real August 2024 Registry Fixture",
            document_type=DocumentType.MASTER_CIRCULAR,
            status=DocumentStatus.PROCESSED,
        )
        circular = RegulatoryDocument(
            title="Real June 2025 Circular Fixture",
            document_type=DocumentType.MASTER_CIRCULAR,
            status=DocumentStatus.PROCESSED,
        )
        private_document = RegulatoryDocument(
            organization_id=real.id,
            title="Tenant A private operating manual",
            document_type=DocumentType.OTHER,
            status=DocumentStatus.PROCESSED,
            full_text="PRIVATE RAW DOCUMENT TEXT",
        )
        db.add_all((registry, circular, private_document))
        await db.flush()

        clause = Clause(
            document_id=registry.id,
            clause_number="1",
            text_content="Real source clause used by the registry fixture.",
        )
        db.add(clause)
        await db.flush()
        obligation_texts: list[str] = []
        for spec, count in zip(CONTROL_CATALOG, _CONTROL_OBLIGATION_COUNTS, strict=True):
            for index in range(count):
                obligation_texts.append(f"{spec.match_any[index % len(spec.match_any)]} fixture")
        obligation_texts.extend(f"unmapped real fixture duty {index}" for index in range(12))
        assert len(obligation_texts) == 45
        for index, obligation_text in enumerate(obligation_texts):
            db.add(
                Obligation(
                    document_id=registry.id,
                    clause_id=clause.id,
                    source_text=clause.text_content,
                    normalized_obligation=obligation_text,
                    risk_level=RiskLevel.HIGH if index < 5 else RiskLevel.MEDIUM,
                )
            )

        run = DiffRun(
            old_document_id=registry.id,
            new_document_id=circular.id,
            status=DiffRunStatus.COMPLETED,
        )
        db.add(run)
        await db.flush()
        for reference in ("§17", "§71", "§72", "§88"):
            db.add(
                RegulatoryChange(
                    diff_run_id=run.id,
                    old_document_id=registry.id,
                    new_document_id=circular.id,
                    change_type=ChangeType.CREATED,
                    description="deterministic fixture change",
                    materiality=MaterialityLevel.HIGH
                    if reference == "§17"
                    else MaterialityLevel.MEDIUM,
                    diff_details={
                        "new_ref": reference,
                        "obligation": (
                            "Framework for Monitoring and Supervision of System Audit"
                            if reference == "§17"
                            else f"Public circular gap type {reference}"
                        ),
                    },
                )
            )
        db.add(
            RegulatoryChange(
                diff_run_id=run.id,
                old_document_id=registry.id,
                new_document_id=circular.id,
                change_type=ChangeType.MODIFIED,
                description="terminology cleanup",
                materiality=MaterialityLevel.LOW,
                diff_details={"old_ref": "§31", "new_ref": "§32", "obligation": "cleanup"},
            )
        )
        private_control = Control(
            organization_id=real.id,
            name="System-audit monitoring and supervision control",
            description="PRIVATE CONTROL DESCRIPTION",
            status="active",
            metadata_json={
                "source": "phase3_real_change_seed",
                "source_topic": "Framework for Monitoring and Supervision of System Audit",
            },
        )
        db.add(private_control)
        await db.flush()
        await db.commit()

        first = await seed_suptech(
            db,
            supervisor_password="phase5-test-password",
            real_org_id=real.id,
            registry_document_id=registry.id,
            circular_id=circular.id,
            expected_registry_count=45,
        )
        await db.commit()
        before_second = await _count_seed_rows()
        second = await seed_suptech(
            db,
            supervisor_password="phase5-test-password",
            real_org_id=real.id,
            registry_document_id=registry.id,
            circular_id=circular.id,
            expected_registry_count=45,
        )
        await db.commit()
        after_second = await _count_seed_rows()
        assert first.registry_obligations == 45
        assert first.tracked_changes == 4
        assert second.created == {}
        assert before_second == after_second

        first_layer = await build_tenant_a_layer(db, as_of=date(2026, 8, 9), tenant_id=real.id)
        await db.commit()
        second_layer = await build_tenant_a_layer(db, as_of=date(2026, 8, 9), tenant_id=real.id)
        await db.commit()
        assert first_layer.catalogue_controls == 15
        assert first_layer.mapped_obligations == 33
        assert first_layer.evidence_valid == 28
        assert first_layer.evidence_stale == 4
        assert first_layer.evidence_missing == 13
        assert first_layer.adopted_references == ("§17",)
        assert set(first_layer.blocked_references) == {"§71", "§72", "§88"}
        assert second_layer.created == {}

        viewer = (
            await db.execute(
                select(User).where(User.email == "supervisory.viewer@circularos.local")
            )
        ).scalar_one()
        supervisor = (
            await db.execute(
                select(Organization).where(Organization.slug == "sebi-supervisory-mirror")
            )
        ).scalar_one()
        return SupTechFixture(
            token=create_access_token(viewer.id, supervisor.id, UserRole.SUPERVISORY_VIEWER.value),
            circular_id=circular.id,
            private_document_id=private_document.id,
            private_control_id=private_control.id,
        )


@pytest.fixture(scope="module")
def suptech_fixture(client: TestClient) -> SupTechFixture:
    return asyncio.run(_prepare_suptech_fixture())


def _headers(fixture: SupTechFixture) -> dict[str, str]:
    return {"Authorization": f"Bearer {fixture.token}"}


def _assert_aggregate_only(value: object) -> None:
    forbidden = {
        "full_text",
        "text_content",
        "source_text",
        "old_text",
        "new_text",
        "description",
        "control_description",
        "file_path",
        "mapping_rationale",
        "cited_text",
        "extracted_facts",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            _assert_aggregate_only(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_aggregate_only(nested)


def test_posture_is_live_labelled_and_aggregate_only(
    client: TestClient, suptech_fixture: SupTechFixture
) -> None:
    response = client.get("/api/v1/suptech/posture", headers=_headers(suptech_fixture))
    assert response.status_code == 200
    payload = response.json()
    assert payload["market_rollup"]["intermediaries"] == 3
    assert payload["market_rollup"]["real_intermediaries"] == 1
    assert payload["market_rollup"]["seeded_intermediaries"] == 2
    by_name = {item["name"]: item for item in payload["intermediaries"]}
    assert by_name["Tenant A — Real Registry"]["seeded"] is False
    as_of = date.fromisoformat(payload["as_of"])
    expected_freshness = {"valid": 0, "stale": 0, "missing": 12}
    for spec, count in zip(CONTROL_CATALOG, _CONTROL_OBLIGATION_COUNTS, strict=True):
        seeded_freshness = plan_control_freshness(spec, date(2026, 8, 9))
        if seeded_freshness is None:
            expected_freshness["missing"] += count
            continue
        current_freshness = calculate_freshness(
            seeded_freshness.collection_date,
            spec.frequency_days,
            as_of,
        )
        if current_freshness.status == EvidenceStatus.VALID:
            expected_freshness["valid"] += count
        else:
            expected_freshness["stale"] += count
    real_posture = by_name["Tenant A — Real Registry"]
    assert real_posture["evidence_freshness"] == expected_freshness
    assert real_posture["coverage"]["percentage"] == round(
        expected_freshness["valid"] / 45 * 100,
        2,
    )
    assert real_posture["open_gaps"]["total"] == (
        expected_freshness["stale"] + expected_freshness["missing"]
    )
    assert by_name["Tenant B — Well Implemented (Seeded)"]["coverage"]["percentage"] == 66.67
    assert by_name["Tenant C — Laggard (Seeded)"]["coverage"]["percentage"] == 11.11
    _assert_aggregate_only(payload)


def test_adoption_uses_four_real_material_change_rows(
    client: TestClient, suptech_fixture: SupTechFixture
) -> None:
    response = client.get(
        f"/api/v1/suptech/adoption/{suptech_fixture.circular_id}",
        headers=_headers(suptech_fixture),
    )
    assert response.status_code == 200
    payload = response.json()
    assert {item["reference"] for item in payload["changes"]} == {"§17", "§71", "§72", "§88"}
    assert all(item["reference"] != "§32" for item in payload["changes"])
    by_name = {item["name"]: item for item in payload["intermediaries"]}
    assert by_name["Tenant A — Real Registry"]["adoption_percentage"] == 25.0
    assert by_name["Tenant B — Well Implemented (Seeded)"]["adoption_percentage"] == 100.0
    assert by_name["Tenant C — Laggard (Seeded)"]["adoption_percentage"] == 25.0
    _assert_aggregate_only(payload)


def test_gap_drilldown_has_names_and_posture_but_no_raw_fields(
    client: TestClient, suptech_fixture: SupTechFixture
) -> None:
    adoption = client.get(
        f"/api/v1/suptech/adoption/{suptech_fixture.circular_id}",
        headers=_headers(suptech_fixture),
    ).json()
    gap_key = next(item["gap_key"] for item in adoption["changes"] if item["reference"] == "§71")
    response = client.get(f"/api/v1/suptech/gaps/{gap_key}", headers=_headers(suptech_fixture))
    assert response.status_code == 200
    payload = response.json()
    assert payload["gap"]["kind"] == "circular_adoption"
    assert {item["name"] for item in payload["intermediaries"]} == {
        "Tenant A — Real Registry",
        "Tenant C — Laggard (Seeded)",
    }
    _assert_aggregate_only(payload)


def test_supervisor_is_denied_other_org_raw_document_and_control(
    client: TestClient, suptech_fixture: SupTechFixture
) -> None:
    document_response = client.get(
        f"/api/v1/documents/{suptech_fixture.private_document_id}",
        headers=_headers(suptech_fixture),
    )
    control_response = client.get(
        f"/api/v1/controls/{suptech_fixture.private_control_id}",
        headers=_headers(suptech_fixture),
    )
    assert document_response.status_code == 403
    assert control_response.status_code == 403
    assert "aggregate SupTech endpoints only" in document_response.json()["detail"]


def test_suptech_endpoint_requires_supervisory_viewer(client: TestClient) -> None:
    assert client.get("/api/v1/suptech/posture").status_code == 401
