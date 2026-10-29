from concurrent.futures import Future

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.session import engine
from app.main import app
from app.modules.audit.models import RuleEvaluation
from app.modules.fit.schemas import RequirementAssessmentProposal
from app.modules.opportunities.models import Opportunity
from app.modules.opportunities.schemas import JDExtractionProposal, JDExtractionProviderResult
from app.web import routes, workflow

RAW = {
    "company": "Synthetic UI company",
    "role_title": "Project manager",
    "raw_text": "Project management experience is required.",
}


class ImmediateExecutor:
    def submit(self, fn, *args):
        future = Future()
        future.set_result(fn(*args))
        return future


class FakeExtractor:
    def extract_with_telemetry(self, *, request, **kwargs):
        return JDExtractionProviderResult(
            proposal=JDExtractionProposal(
                requirements=[
                    {
                        "requirement_key": "project_management",
                        "description": "Project management experience",
                        "priority": "MUST_HAVE",
                        "category": "EXPERIENCE",
                        "criterion_type": "ESSENTIAL",
                        "classification_reason": "The source explicitly says required.",
                        "blocking": False,
                        "evidence_text": request.raw_text,
                    }
                ]
            ),
            telemetry={
                "provider_name": "synthetic",
                "provider_version": "1",
                "model_name": "synthetic",
                "latency_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
            },
        )


class FakeAssessor:
    provider_name = "synthetic"
    provider_version = "1"
    calls = 0

    def propose(self, *, request):
        self.calls += 1
        primary = next((e for e in request.ranked_evidence if e.tier == "PRIMARY"), None)
        return RequirementAssessmentProposal(
            requirement_key=request.requirement.requirement_key,
            proposed_status="MATCH" if primary else "UNKNOWN",
            evidence=[{"profile_fact_id": primary.profile_fact_id}] if primary else [],
            rationale="Synthetic response; no real model call.",
        )


@pytest.fixture
def browser_client(monkeypatch):
    assessor = FakeAssessor()
    monkeypatch.setattr(routes, "executor", ImmediateExecutor())
    monkeypatch.setattr(workflow, "make_extractor", lambda: FakeExtractor())
    monkeypatch.setattr(workflow, "make_assessor", lambda: assessor)
    routes.jobs.clear()
    with TestClient(app) as client:
        yield client, assessor
    routes.jobs.clear()


def approved(client):
    response = client.post("/api/jobs", json=RAW)
    assert response.status_code == 202
    job_id = response.json()["id"]
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "extracted"
    response = client.post(
        f"/api/jobs/{job_id}/review",
        json={"reviewer": "Synthetic reviewer", "reviewed_keys": ["project_management"]},
    )
    assert response.status_code == 200
    return job_id


def test_preview_rolls_back_and_save_keeps_exact_result_without_model_repeat(browser_client):
    client, assessor = browser_client
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(Opportunity))
    job_id = approved(client)
    assert client.post(f"/api/jobs/{job_id}/evaluate").status_code == 202
    data = client.get(f"/api/jobs/{job_id}").json()
    assert data["state"] == "complete"
    assert not data["report"]["persisted"]
    assert data["report"]["assessments"][0]["evidence_items"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Opportunity)) == before
    response = client.post(f"/api/jobs/{job_id}/save")
    assert response.status_code == 200
    first = response.json()["opportunity_id"]
    assert client.post(f"/api/jobs/{job_id}/save").json()["opportunity_id"] == first
    assert assessor.calls == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Opportunity)) == before + 1
        audits = session.scalars(
            select(RuleEvaluation).where(RuleEvaluation.entity_id == first)
        ).all()
        assert len(audits) == 3
        report = next(a.result_json for a in audits if a.rule_set == "reviewed_web_report")
        assert report["score"] == data["report"]["score"]
        assert report["assessments"] == data["report"]["assessments"]
    assert (
        client.post(
            f"/api/jobs/{job_id}/review",
            json={"reviewer": "Other", "reviewed_keys": ["project_management"]},
        ).status_code
        == 409
    )


def test_incomplete_review_and_ungrounded_edits_cannot_be_evaluated(browser_client):
    client, _ = browser_client
    job_id = client.post("/api/jobs", json=RAW).json()["id"]
    assert client.post(f"/api/jobs/{job_id}/evaluate").status_code == 409
    assert client.post(f"/api/jobs/{job_id}/save").status_code == 409
    assert (
        client.post(
            f"/api/jobs/{job_id}/review", json={"reviewer": "Tester", "reviewed_keys": []}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/jobs/{job_id}/review",
            json={
                "reviewer": "Tester",
                "reviewed_keys": ["project_management"],
                "amendments": [
                    {
                        "requirement_key": "project_management",
                        "evidence_text": "Invented source evidence",
                        "reason": "Test rejection",
                    }
                ],
            },
        ).status_code
        == 422
    )


def test_changed_review_invalidates_old_report(browser_client):
    client, _ = browser_client
    job_id = approved(client)
    client.post(f"/api/jobs/{job_id}/evaluate")
    assert client.get(f"/api/jobs/{job_id}").json()["report"]
    response = client.post(
        f"/api/jobs/{job_id}/review",
        json={"reviewer": "Tester", "reviewed_keys": ["project_management"], "note": "Revised"},
    )
    assert response.status_code == 200
    assert client.get(f"/api/jobs/{job_id}").json()["report"] is None
    assert client.post(f"/api/jobs/{job_id}/save").status_code == 409


def test_errors_are_visible_and_audit_is_downloadable(browser_client, monkeypatch):
    client, _ = browser_client

    def broken(raw, checkpoint):
        checkpoint({"status": "failed", "attempts": [{"error": "Invalid literal quote"}]})
        raise ValueError("Invalid literal quote")

    monkeypatch.setattr(workflow, "extract", broken)
    job_id = client.post("/api/jobs", json=RAW).json()["id"]
    data = client.get(f"/api/jobs/{job_id}").json()
    assert data["state"] == "failed"
    assert data["error"] == "Invalid literal quote"
    response = client.get(f"/api/jobs/{job_id}/download")
    assert response.json()["extraction_audit"]["status"] == "failed"
    assert "attachment" in response.headers["content-disposition"]


def test_local_origin_host_and_assets(browser_client):
    client, _ = browser_client
    assert (
        client.post(
            "/api/jobs", json=RAW, headers={"origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert client.get("/", headers={"host": "untrusted.example"}).status_code == 400
    page = client.get("/")
    assert page.status_code == 200
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/ui/app.js").status_code == 200
    assert client.get("/ui/unknown.txt").status_code == 404
    assert client.get("/api/jobs/not-found").status_code == 404


def test_literal_source_error_is_explained_and_technical_detail_is_retained(
    browser_client, monkeypatch
):
    client, _ = browser_client
    technical = "Requirement evidence_text must be a verbatim contiguous substring of the Job Description raw_text. Requirement: 'barcelona_hybrid_location'."

    def broken(raw, checkpoint):
        raise ValueError(technical)

    monkeypatch.setattr(workflow, "extract", broken)
    job_id = client.post("/api/jobs", json=RAW).json()["id"]
    data = client.get(f"/api/jobs/{job_id}").json()
    assert "cita literal" in data["error"]
    assert "No s'ha desat cap oportunitat" in data["error"]
    assert "barcelona_hybrid_location" in data["error"]
    assert "verbatim contiguous substring" not in data["error"]
    assert client.get(f"/api/jobs/{job_id}/download").json()["technical_error"] == technical


def test_segmented_context_is_stored_but_never_sent_to_assessor(browser_client, monkeypatch):
    from app.modules.opportunities.models import JobRequirement
    from app.modules.opportunities.schemas import JobDescriptionInput, JobRequirementInput

    client, assessor = browser_client
    source = "Our mission is innovation. Project management is required. Jira is preferred. Lead delivery teams."
    types = [
        ("mission", "CONTEXT", "Our mission is innovation."),
        ("pm", "ESSENTIAL", "Project management is required."),
        ("jira", "DESIRABLE", "Jira is preferred."),
        ("delivery", "ROLE_CAPABILITY", "Lead delivery teams."),
    ]
    job = JobDescriptionInput(
        company="Synthetic",
        role_title="Lead",
        raw_text=source,
        requirements=[
            JobRequirementInput(
                requirement_key=key,
                description=quote,
                criterion_type=kind,
                classification_reason="Explicit synthetic source wording",
                priority="MUST_HAVE"
                if kind == "ESSENTIAL"
                else "NICE_TO_HAVE"
                if kind == "DESIRABLE"
                else "SECONDARY",
                category="RESPONSIBILITY"
                if kind in {"CONTEXT", "ROLE_CAPABILITY"}
                else "EXPERIENCE",
                evidence_text=quote,
            )
            for key, kind, quote in types
        ],
    )
    monkeypatch.setattr(workflow, "extract", lambda raw, checkpoint: job)
    job_id = client.post("/api/jobs", json=RAW).json()["id"]
    assert (
        client.post(
            f"/api/jobs/{job_id}/review",
            json={"reviewer": "Synthetic", "reviewed_keys": [t[0] for t in types]},
        ).status_code
        == 200
    )
    client.post(f"/api/jobs/{job_id}/evaluate")
    data = client.get(f"/api/jobs/{job_id}").json()
    assert data["state"] == "complete", data
    assert assessor.calls == 3
    assert data["report"]["score"] is None
    assert len(data["report"]["role_context"]) == 1
    assert len(data["report"]["role_capabilities"]) == 1
    saved = client.post(f"/api/jobs/{job_id}/save").json()["opportunity_id"]
    with Session(engine) as session:
        stored = session.scalars(
            select(JobRequirement).where(JobRequirement.opportunity_id == saved)
        ).all()
        assert len(stored) == 4
        assert {r.criterion_type for r in stored} == {t[1] for t in types}
    assert assessor.calls == 3


def test_web_reclassification_without_note_automatically_aligns_priority(browser_client):
    client, _ = browser_client
    job_id = client.post("/api/jobs", json=RAW).json()["id"]
    response = client.post(
        f"/api/jobs/{job_id}/review",
        json={
            "reviewer": "Synthetic reviewer",
            "reviewed_keys": ["project_management"],
            "amendments": [
                {"requirement_key": "project_management", "criterion_type": "DESIRABLE"}
            ],
        },
    )
    assert response.status_code == 200, response.text
    exported = client.get(f"/api/jobs/{job_id}/download").json()["review"]
    assert exported["reviewed"]["requirements"][0]["priority"] == "NICE_TO_HAVE"
    assert exported["amendments"][0]["reason"] == ""
    assert exported["original"]["requirements"][0]["criterion_type"] == "ESSENTIAL"
