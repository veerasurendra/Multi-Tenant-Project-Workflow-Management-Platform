from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.dependences import get_current_user
from app.services import content, files
router = APIRouter(tags=["Comments and Files"])
class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    comment: str
    task_id: int | None = None
    project_id: int | None = None
    created_at: datetime
class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    uploaded_by: int
    filename: str
    mime_type: str
    file_size: int
    task_id: int | None = None
    project_id: int | None = None
    uploaded_at: datetime

def install(kind):
    prefix = f"/{kind}s/{{resource_id}}"
    async def add(resource_id: int, payload: schemas.TaskCommentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
        return content.add_comment(db, user, kind, resource_id, payload.comment)
    def listing(resource_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
        content.resource(db, user, kind, resource_id)
        cls = content.comments_model(kind)
        return db.query(cls).filter(getattr(cls, f"{kind}_id") == resource_id).order_by(cls.created_at, cls.id).all()
    def update(resource_id: int, comment_id: int, payload: schemas.TaskCommentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
        return content.modify_comment(db, user, kind, resource_id, comment_id, payload.comment)
    def delete(resource_id: int, comment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
        content.modify_comment(db, user, kind, resource_id, comment_id, delete=True)
    async def upload(resource_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
        return await files.upload(db, user, kind, resource_id, file)
    def attachments(resource_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
        content.resource(db, user, kind, resource_id)
        cls = models.TaskAttachment if kind == "task" else models.ProjectAttachment
        return db.query(cls).filter(getattr(cls, f"{kind}_id") == resource_id).all()
    def download(resource_id: int, attachment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
        row = files.attachment(db, user, kind, resource_id, attachment_id)
        return FileResponse(row.filepath, media_type=row.mime_type, filename=row.filename)
    for endpoint, suffix, methods, response, code in [
        (add, "/comments", ["POST"], CommentOut, 201), (listing, "/comments", ["GET"], list[CommentOut], 200),
        (update, "/comments/{comment_id}", ["PUT", "PATCH"], CommentOut, 200), (delete, "/comments/{comment_id}", ["DELETE"], None, 204),
        (upload, "/attachments", ["POST"], AttachmentOut, 201), (attachments, "/attachments", ["GET"], list[AttachmentOut], 200),
        (download, "/attachments/{attachment_id}/download", ["GET"], None, 200)]:
        for method in methods:
            router.add_api_route(prefix+suffix, endpoint, methods=[method], response_model=response, status_code=code, name=f"{kind}_{endpoint.__name__}_{method.lower()}")
install("task")
install("project")
