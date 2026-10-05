import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.routers import auth, members, projects, tasks, users, notification, activitylog, audit, organizations, content, dashboard
from app.services.reminders import loop

@asynccontextmanager
async def lifespan(app):
    worker = asyncio.create_task(loop()) if settings.REMINDERS_ENABLED else None
    yield
    if worker:
        worker.cancel()
        with suppress(asyncio.CancelledError): await worker

app = FastAPI(title=settings.APP_NAME, version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def error_response(code, message, status, headers=None, details=None):
    error = {"code": code, "message": message}
    if details is not None: error["details"] = details
    return JSONResponse({"success": False, "error": error}, status_code=status, headers=headers)

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    codes = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "ACCESS_DENIED", 404: "NOT_FOUND", 409: "CONFLICT", 413: "FILE_TOO_LARGE", 422: "VALIDATION_ERROR"}
    return error_response(codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail), exc.status_code, exc.headers)
@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    details = [{"location": list(e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()]
    return error_response("VALIDATION_ERROR", "Request validation failed", 422, details=details)
@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return error_response("CONFLICT", "The request conflicts with existing records", 409)
@app.exception_handler(Exception)
async def internal_error(request, exc):
    logging.getLogger(__name__).exception("Unhandled API error")
    return error_response("INTERNAL_ERROR", "An unexpected error occurred", 500)

for router in (auth.router, projects.router, members.router, tasks.router, users.router, notification.router,
               activitylog.router, audit.router, organizations.router, content.router, dashboard.router):
    app.include_router(router, prefix="/api")
    app.include_router(router, include_in_schema=False)

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
