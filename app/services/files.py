import io
import uuid
from pathlib import Path
from fastapi import HTTPException
from app import models
from app.config import settings
from app.services.content import resource
from app.services.events import record

# A narrow allowlist makes validation deterministic. Arbitrary binaries and archives are rejected.
MIME = {".txt": "text/plain", ".csv": "text/csv", ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

def validate(filename, declared, data):
    extension = Path(filename).suffix.lower()
    mime = MIME.get(extension)
    if not mime: raise HTTPException(400, "Unsupported file extension")
    if not data: raise HTTPException(400, "Empty files are not allowed")
    if len(data) > settings.MAX_UPLOAD_BYTES: raise HTTPException(413, "File exceeds maximum size")
    if declared != mime: raise HTTPException(400, "MIME type does not match the file extension")
    if extension in {".txt", ".csv"}:
        try: text = data.decode("utf-8")
        except UnicodeDecodeError: raise HTTPException(400, "Text files must contain UTF-8 text")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text): raise HTTPException(400, "Invalid text content")
        if text.lstrip().lower().startswith(("<html", "<!doctype html", "<script", "<?php")):
            raise HTTPException(400, "Executable markup is not allowed")
    elif extension == ".pdf":
        from pypdf import PdfReader
        try:
            if not data.startswith(b"%PDF-"): raise ValueError()
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or not reader.pages: raise ValueError()
            root = reader.trailer["/Root"]
            if any(k in root for k in ("/OpenAction", "/AA", "/Names")): raise ValueError()
        except Exception: raise HTTPException(400, "Invalid or active PDF content")
    else:
        from PIL import Image
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format != ("PNG" if extension == ".png" else "JPEG"): raise ValueError()
                if image.width * image.height > 25_000_000: raise ValueError()
                image.verify()
        except Exception: raise HTTPException(400, "Invalid image content")
    return mime

async def upload(db, actor, kind, resource_id, file):
    resource(db, actor, kind, resource_id, True)
    filename = Path((file.filename or "").replace("\\", "/")).name.strip()
    if not filename or len(filename) > 255: raise HTTPException(400, "Invalid filename")
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    mime = validate(filename, file.content_type, data)
    directory = Path(settings.UPLOAD_DIR).resolve(); directory.mkdir(parents=True, exist_ok=True)
    path = directory / (uuid.uuid4().hex + Path(filename).suffix.lower())
    path.write_bytes(data)
    cls = models.TaskAttachment if kind == "task" else models.ProjectAttachment
    row = cls(**{f"{kind}_id": resource_id}, uploaded_by=actor.id, filename=filename, filepath=str(path), mime_type=mime, file_size=len(data))
    try:
        db.add(row); db.flush()
        record(db, actor, "FILE_UPLOADED", kind.title(), resource_id, {"attachment_id": row.id, "filename": filename})
        db.commit(); db.refresh(row)
    except Exception:
        db.rollback(); path.unlink(missing_ok=True); raise
    return row

def attachment(db, actor, kind, resource_id, attachment_id):
    resource(db, actor, kind, resource_id)
    cls = models.TaskAttachment if kind == "task" else models.ProjectAttachment
    row = db.query(cls).filter(cls.id == attachment_id, getattr(cls, f"{kind}_id") == resource_id).first()
    if not row: raise HTTPException(404, "Attachment not found")
    path = Path(row.filepath).resolve(); directory = Path(settings.UPLOAD_DIR).resolve()
    if not path.is_relative_to(directory) or not path.is_file(): raise HTTPException(404, "File not found")
    return row
