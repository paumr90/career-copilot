"""Single-user local browser workflow; no personal data is kept in browser storage."""

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.modules.opportunities.coverage import extraction_coverage
from app.modules.opportunities.review import (
    RequirementAmendment,
    RequirementReviewRequest,
    RequirementReviewService,
)
from app.modules.opportunities.schemas import RawJobDescriptionInput
from app.web import workflow

router = APIRouter()

static = Path(__file__).parent / "static"

executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="local-preview")

jobs = {}

lock = threading.RLock()


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1)

    reviewed_keys: list[str]

    amendments: list[RequirementAmendment] = Field(default_factory=list)

    note: str = ""


def get_job(job_id):

    if job_id not in jobs:
        raise HTTPException(
            404, "La sessió no existeix o el servidor s'ha reiniciat. Torna a enganxar l'oferta."
        )

    return jobs[job_id]


def public(job):

    return {
        key: value
        for key, value in job.items()
        if key in {"id", "state", "error", "job", "coverage", "report", "saved_id", "review_hash"}
    }


def friendly_error(error):
    text = str(error)
    if "evidence_text must be a verbatim contiguous substring" in text:
        match = re.search(r"Requirement: '([^']+)'", text)
        criterion = f" ({match.group(1)})" if match else ""
        return (
            "No s'ha pogut vincular un requisit"
            + criterion
            + " a una cita literal de l'oferta després de l'intent de correcció. "
            "Comprova que el text complet inclogui la ubicació i la modalitat; "
            "el camp Ubicació no substitueix el text original. "
            "No s'ha desat cap oportunitat. Pots descarregar l'auditoria i tornar a extreure."
        )
    return (
        text
        if isinstance(error, ValueError)
        else "No s'ha pogut completar l'operació. Comprova PostgreSQL, la connexió i la configuració de la IA."
    )


def run(job_id, operation):

    try:
        operation()

    except Exception as error:  # noqa: BLE001 - retain failure without exposing credentials
        with lock:
            job = get_job(job_id)

            job["state"] = "failed"

            job["error"] = friendly_error(error)
            job["technical_error"] = (
                str(error) if isinstance(error, ValueError) else type(error).__name__
            )

            job["assessment_attempts"] = getattr(error, "assessment_attempts", [])


@router.get("/")
def index():

    return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})


@router.get("/ui/{filename}")
def asset(filename: str):

    if filename not in {"app.js", "style.css"}:
        raise HTTPException(404)

    return FileResponse(static / filename)


@router.post("/api/jobs", status_code=202)
def start(raw: RawJobDescriptionInput):

    with lock:
        if len(jobs) >= 30:
            raise HTTPException(
                409,
                "Límit de 30 sessions temporals. Reinicia el servidor després de desar o descarregar els resultats.",
            )

        job_id = str(uuid.uuid4())

        job = jobs[job_id] = {"id": job_id, "state": "extracting", "error": None, "saved_id": None}

    def operation():

        def checkpoint(audit):

            with lock:
                job["extraction_audit"] = audit

        extracted = workflow.extract(raw, checkpoint)

        with lock:
            job.update(
                state="extracted",
                job=extracted.model_dump(mode="json"),
                coverage=extraction_coverage(extracted),
            )

    executor.submit(run, job_id, operation)

    return {"id": job_id, "state": "extracting"}


@router.get("/api/jobs/{job_id}")
def status(job_id: str):

    with lock:
        return public(get_job(job_id))


@router.post("/api/jobs/{job_id}/review")
def review(job_id: str, values: ReviewInput):

    with lock:
        job = get_job(job_id)

        if (
            job["state"] not in {"extracted", "reviewed", "complete", "failed"}
            or "job" not in job
            or job["saved_id"]
        ):
            raise HTTPException(409, "No es pot modificar aquesta revisió ara.")

        try:
            approved = RequirementReviewService().review(
                RequirementReviewRequest(job=job["job"], **values.model_dump())
            )

        except ValueError as error:
            raise HTTPException(422, str(error)) from error

        job.update(
            approved=approved,
            state="reviewed",
            report=None,
            snapshots=None,
            error=None,
            review_hash=approved.review_hash,
        )

        return {"review_hash": approved.review_hash}


@router.post("/api/jobs/{job_id}/evaluate", status_code=202)
def evaluate(job_id: str):

    with lock:
        job = get_job(job_id)

        if job["state"] != "reviewed":
            raise HTTPException(409, "Revisa i confirma tots els requisits abans d'avaluar.")

        job.update(state="evaluating", error=None)

    def operation():

        report, snapshots = workflow.evaluate(job["approved"])

        with lock:
            job.update(report=report, snapshots=snapshots, state="complete")

    executor.submit(run, job_id, operation)

    return {"state": "evaluating"}


@router.post("/api/jobs/{job_id}/save")
def save(job_id: str):

    with lock:
        job = get_job(job_id)

        if job["saved_id"]:
            return {"opportunity_id": job["saved_id"], "persisted": True}

        if job["state"] != "complete":
            raise HTTPException(409, "Cal una avaluació completada abans de desar.")

        try:
            job["saved_id"] = workflow.save(job["approved"], job["report"], job["snapshots"])

        except Exception as error:
            raise HTTPException(503, "No s'ha pogut desar. Pots tornar-ho a provar.") from error

        job["report"]["persisted"] = True

        return {"opportunity_id": job["saved_id"], "persisted": True}


@router.get("/api/jobs/{job_id}/download")
def download(job_id: str):

    with lock:
        job = get_job(job_id)

        payload = {
            key: job[key]
            for key in (
                "job",
                "report",
                "extraction_audit",
                "assessment_attempts",
                "saved_id",
                "technical_error",
            )
            if key in job
        }

        if "approved" in job:
            payload["review"] = job["approved"].model_dump(mode="json")

        return Response(
            json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="career-copilot.local.json"',
                "Cache-Control": "no-store",
            },
        )


async def local_request_guard(request: Request, call_next):

    # The app has no authentication: bind to loopback and reject cross-origin writes.

    if request.url.path.startswith("/api/") and request.method == "POST":
        origin = request.headers.get("origin")

        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return Response("Origen no permès", status_code=403)

    response = await call_next(request)

    response.headers["Cache-Control"] = "no-store"

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )

    return response
