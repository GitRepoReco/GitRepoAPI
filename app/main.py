import os
from typing import Any

import psycopg2
from fastapi import FastAPI, HTTPException, Query
from psycopg2.extras import RealDictCursor

app = FastAPI(title="GitRepoReco API", version="1.0.0")


def get_db_config() -> dict[str, Any]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB", "github_data"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }


def get_connection():
    config = get_db_config()
    return psycopg2.connect(**config, connect_timeout=10)


@app.get("/")
def read_root() -> dict[str, Any]:
    return {
        "service": "GitRepoReco API",
        "message": "Use /repositories or /repositories/top to fetch the top GitHub repositories.",
    }


@app.get("/health")
def healthcheck() -> dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - defensive guard for runtime DB failure
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/repositories")
@app.get("/repositories/top")
def list_top_repositories(
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    query = "SELECT * FROM github.repositories ORDER BY stars DESC, updated_at DESC LIMIT %s"

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                rows = cur.fetchall()

        return {
            "limit": limit,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }
    except Exception as exc:  # pragma: no cover - defensive guard for runtime DB failure
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
