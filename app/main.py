import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg2
from fastapi import APIRouter, FastAPI, HTTPException, Query
from psycopg2.extras import RealDictCursor
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = os.getenv("APP_VERSION", "dev")

start_time = datetime.now()

app = FastAPI(title="GitRepoReco API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200/",               # dev Angular
        "http://api.reporeco.duckdns.org/",     # site de l'api
        "http://reporeco.duckdns.org/",         # site principal
        "http://api.gitreporeco.duckdns.org/",  # API GitRepoReco
        "http://gitreporeco.duckdns.org/",      # site principal GitRepoReco
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

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


def _serialize_value(v: Any) -> Any:
    if isinstance(v, timedelta):
        total = int(v.total_seconds())
        sign = "-" if total < 0 else ""
        h, rem = divmod(abs(total), 3600)
        m, s = divmod(rem, 60)
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _serialize_row(row: dict) -> dict:
    return {k: _serialize_value(v) for k, v in row.items()}


def _serialize_rows(rows: list) -> list:
    return [_serialize_row(dict(r)) for r in rows]


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
        return {"status": "ok", "uptime": str(datetime.now() - start_time)}
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

@app.get("/version")
async def get_version():
    return {
        "version": APP_VERSION
    }


# ---------------------------------------------------------------------------
# Monitoring router
# ---------------------------------------------------------------------------

monitoring_router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@monitoring_router.get("/general")
def monitoring_general() -> dict[str, Any]:
    """Informations générales sur l'instance PostgreSQL."""
    query = """
        SELECT
            version()                              AS version,
            pg_postmaster_start_time()             AS start_time,
            NOW() - pg_postmaster_start_time()     AS uptime,
            current_setting('max_connections')::int AS max_connections,
            (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') AS active_connections,
            (SELECT count(*) FROM pg_stat_activity)                        AS total_connections
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                row = cur.fetchone()
        return _serialize_row(dict(row))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


@monitoring_router.get("/databases")
def monitoring_databases() -> dict[str, Any]:
    """Taille des bases de données."""
    query = """
        SELECT
            datname                                              AS database,
            pg_database_size(datname)                           AS size_bytes,
            pg_size_pretty(pg_database_size(datname))           AS size
        FROM pg_database
        WHERE datistemplate = false
        ORDER BY pg_database_size(datname) DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return {"count": len(rows), "items": _serialize_rows(rows)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


@monitoring_router.get("/schemas")
def monitoring_schemas() -> dict[str, Any]:
    """Nombre de tables par schéma."""
    query = """
        SELECT
            schemaname,
            count(*) AS table_count
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        GROUP BY schemaname
        ORDER BY schemaname
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return {"count": len(rows), "items": _serialize_rows(rows)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


@monitoring_router.get("/tables")
def monitoring_tables() -> dict[str, Any]:
    """Statistiques des tables utilisateur."""
    query = """
        SELECT
            schemaname,
            relname                                                                   AS table_name,
            n_live_tup                                                                AS estimated_rows,
            n_dead_tup                                                                AS dead_rows,
            seq_scan,
            idx_scan,
            n_tup_ins                                                                 AS inserts,
            n_tup_upd                                                                 AS updates,
            n_tup_del                                                                 AS deletes,
            pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) AS total_size_bytes,
            pg_indexes_size(quote_ident(schemaname) || '.' || quote_ident(relname))        AS index_size_bytes
        FROM pg_stat_user_tables
        ORDER BY pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return {"count": len(rows), "items": _serialize_rows(rows)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


@monitoring_router.get("/cache")
def monitoring_cache() -> dict[str, Any]:
    """Taux de cache (buffer hit ratio) global."""
    query = """
        SELECT
            sum(blks_hit)   AS cache_hits,
            sum(blks_read)  AS disk_reads,
            ROUND(
                100.0 * sum(blks_hit) /
                NULLIF(sum(blks_hit) + sum(blks_read), 0),
                2
            ) AS cache_hit_ratio
        FROM pg_stat_database
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                row = cur.fetchone()
        return _serialize_row(dict(row))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


@monitoring_router.get("/active-queries")
def monitoring_active_queries() -> dict[str, Any]:
    """Requêtes actuellement en cours d'exécution."""
    query = """
        SELECT
            pid,
            datname,
            usename,
            state,
            now() - query_start          AS duration,
            wait_event_type,
            wait_event,
            LEFT(query, 200)             AS query
        FROM pg_stat_activity
        WHERE state = 'active'
          AND pid <> pg_backend_pid()
        ORDER BY query_start
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return {"count": len(rows), "items": _serialize_rows(rows)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


@monitoring_router.get("/rate-limit/latest")
def monitoring_rate_limit_latest() -> dict[str, Any]:
    """Dernière entrée de monitoring.rate_limit_usage."""
    query = """
        SELECT
            id,
            timestamp,
            limit_value,
            remaining,
            used,
            cost,
            reset_at,
            operation_name
        FROM monitoring.rate_limit_usage
        ORDER BY timestamp DESC
        LIMIT 1
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No rate limit data found")
        return _serialize_row(dict(row))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to query database: {exc}") from exc


app.include_router(monitoring_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )