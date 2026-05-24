import os
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config.settings import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {".log", ".txt"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload-log")
async def upload_log(file: UploadFile = File(...)):
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[-1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Only .log and .txt files are allowed.",
        )

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.",
        )

    try:
        log_content = contents.decode("utf-8")
    except UnicodeDecodeError:
        try:
            log_content = contents.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="File encoding not supported. Use UTF-8 or Latin-1.")

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)

    async with aiofiles.open(save_path, "w", encoding="utf-8") as f:
        await f.write(log_content)

    return {
        "success": True,
        "data": {
            "filename": filename,
            "log_content": log_content,
            "line_count": len(log_content.splitlines()),
            "file_size_bytes": len(contents),
            "message": "File uploaded successfully. Use POST /api/analyze to analyze this log.",
        },
    }
