from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.infrastructure.db.session import check_database_connection
from app.web.routes import local_request_guard, router

app = FastAPI(
    title="Career Copilot",
    version="0.1.0",
)

app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
)
app.middleware("http")(local_request_guard)
app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    database_status = "ok" if check_database_connection() else "error"

    return {
        "status": "ok",
        "database": database_status,
    }
