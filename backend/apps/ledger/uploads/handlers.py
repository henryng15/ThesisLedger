from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone


def save_uploaded_file(uploaded_file: UploadedFile, destination_dir: str | None = None) -> dict[str, Any]:
    """Persist an uploaded file to MEDIA_ROOT and return a lightweight metadata payload."""
    media_root = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
    if destination_dir:
        media_root = media_root / destination_dir

    media_root.mkdir(parents=True, exist_ok=True)

    filename = uploaded_file.name or "upload"
    target_path = media_root / filename
    counter = 1
    while target_path.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        target_path = media_root / f"{stem}_{counter}{suffix}"
        counter += 1

    with target_path.open("wb+") as handle:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)

    return {
        "filename": filename,
        "path": str(target_path),
        "size": target_path.stat().st_size,
        "uploaded_at": timezone.now().isoformat(),
    }
