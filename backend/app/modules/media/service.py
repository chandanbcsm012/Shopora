"""Business logic for the media module: validated image upload, saved to
a local directory and served back by URL. No database table — this module
exists purely to give the admin panel a place to upload
`Category.image_url` / `ProductImage.url` values (see docs/CONTRACTS.md).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile, status

from app.core.errors import AppError
from app.shared.error_codes import ErrorCode

# Anchored to the backend package regardless of cwd, mirroring how other
# modules avoid depending on the process's working directory.
MEDIA_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "media_storage"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB

# Extension derived from the validated content-type, never from the
# client-supplied filename, to avoid path-traversal/extension-spoofing.
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


async def save_upload(file: UploadFile) -> str:
    """Validate and persist an uploaded image, returning its public URL
    (`/media/<filename>`, served by the StaticFiles mount the Main
    Coordinator wires up over `media_storage/`)."""

    extension = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise AppError(
            ErrorCode.UNSUPPORTED_FILE_TYPE,
            f"Unsupported file type: {file.content_type!r}. "
            f"Accepted types: {', '.join(ALLOWED_CONTENT_TYPES)}.",
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    # 5MB is small enough to safely buffer in memory once; this also lets
    # us check the real size reliably regardless of whether Starlette has
    # populated `UploadFile.size` for this request (spooled files only
    # report it once fully read/rolled over).
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE,
            f"File exceeds the maximum allowed size of {MAX_UPLOAD_BYTES} bytes.",
            status.HTTP_413_CONTENT_TOO_LARGE,
        )

    MEDIA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}.{extension}"
    destination = MEDIA_STORAGE_DIR / filename
    destination.write_bytes(contents)

    return f"/media/{filename}"
