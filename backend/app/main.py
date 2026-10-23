import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.routes import live, transcriptions
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.owner import ensure_owner_cookie

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title="Vaani")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(ensure_owner_cookie)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(transcriptions.router)
app.include_router(live.router)


# Vite content-hashes everything under assets/, so those files never change and can be cached for a year.
# Other files (index.html, the worklet, the favicon) keep stable names and are revalidated via ETag instead.
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
REVALIDATE_CACHE = "no-cache"

# Serve the built frontend; unknown paths fall back to index.html for client-side routing.
dist = settings.frontend_dist
if dist.is_dir():

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        file = (dist / path).resolve()
        if path and file.is_file() and file.is_relative_to(dist.resolve()):
            cache = IMMUTABLE_CACHE if path.startswith("assets/") else REVALIDATE_CACHE
            return FileResponse(file, headers={"Cache-Control": cache})
        return FileResponse(dist / "index.html", headers={"Cache-Control": REVALIDATE_CACHE})
