import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response


SERVICE_URLS = {
    "identity": os.getenv("IDENTITY_URL", "http://localhost:8001"),
    "enrollment": os.getenv("ENROLLMENT_URL", "http://localhost:8002"),
    "faculty": os.getenv("FACULTY_URL", "http://localhost:8003"),
    "admin": os.getenv("ADMIN_URL", "http://localhost:8004"),
}
ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=5.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="NexusEnroll API Gateway",
    version="1.0.0",
    description=(
        "Single public HTTP entry point for the NexusEnroll microservices. "
        "Routes client requests to the appropriate internal service."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_service_url(service: str, path: str, query: str) -> str:
    base_url = SERVICE_URLS[service].rstrip("/")
    target_url = f"{base_url}/{path.lstrip('/')}"
    return f"{target_url}?{query}" if query else target_url


def get_forwarded_headers(request: Request) -> dict[str, str]:
    excluded_headers = {"host", "content-length", "connection"}
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in excluded_headers
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/health/{service}")
async def service_health(service: str, request: Request):
    if service not in SERVICE_URLS:
        raise HTTPException(404, "Unknown service")

    try:
        response = await request.app.state.http_client.get(
            f"{SERVICE_URLS[service]}/health"
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            503, f"{service} service unavailable: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text)
    return response.json()


@app.api_route(
    "/{service}/{path:path}",
    methods=ALLOWED_METHODS,
    include_in_schema=True,
)
async def proxy_request(service: str, path: str, request: Request):
    if service not in SERVICE_URLS:
        raise HTTPException(404, "Unknown service")

    if path == "internal" or path.startswith("internal/"):
        raise HTTPException(404, "Endpoint not available through public API")

    if service == "identity" and request.method != "GET":
        raise HTTPException(404, "Endpoint not available through public API")

    request_body = await request.body()
    target_url = build_service_url(service, path, request.url.query)

    try:
        response = await request.app.state.http_client.request(
            request.method,
            target_url,
            content=request_body,
            headers=get_forwarded_headers(request),
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            504, f"{service} service timed out"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            503, f"{service} service unavailable: {exc}"
        ) from exc

    response_headers = {}
    content_type = response.headers.get("content-type")
    if content_type:
        response_headers["content-type"] = content_type

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
    )
