from fastapi import FastAPI

from app.infrastructure.db.session import check_database_connection

app = FastAPI(
    title="Career Copilot",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    database_status = "ok" if check_database_connection() else "error"

    return {
        "status": "ok",
        "database": database_status,
    }
