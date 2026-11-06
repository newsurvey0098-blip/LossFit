"""Private, owner-scoped image storage for local development and Vercel."""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4

ImageKind = Literal["food", "scan"]
_BLOB_REFERENCE = re.compile(r"^blob:users/([1-9][0-9]*)/(food|scan)/([a-f0-9]{32})\.jpg$")


def blob_storage_enabled() -> bool:
    return bool(
        os.getenv("BLOB_STORE_ID")
        or os.getenv("BLOB_READ_WRITE_TOKEN")
        or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN")
    )


def _pathname(reference: str, owner_id: int, kind: ImageKind) -> str:
    match = _BLOB_REFERENCE.fullmatch(reference)
    if not match or int(match.group(1)) != owner_id or match.group(2) != kind:
        raise FileNotFoundError("Private image not found")
    return reference.removeprefix("blob:")


def _local_path(reference: str, owner_id: int, kind: ImageKind) -> Path:
    root = Path(os.getenv("PRIVATE_UPLOAD_DIR", ".local/uploads")).resolve()
    path = Path(reference).resolve()
    if root not in path.parents or path.parent != (root / str(owner_id) / kind).resolve():
        raise FileNotFoundError("Private image not found")
    return path


async def store_private_image(owner_id: int, kind: ImageKind, content: bytes) -> str:
    if owner_id < 1 or kind not in ("food", "scan"):
        raise ValueError("Invalid private image owner or category")
    filename = f"{uuid4().hex}.jpg"
    if blob_storage_enabled():
        from vercel import blob

        pathname = f"users/{owner_id}/{kind}/{filename}"
        result = await blob.put_blob(
            pathname,
            content,
            access="private",
            content_type="image/jpeg",
            add_random_suffix=False,
            cache_control_max_age=60,
        )
        return f"blob:{result.pathname}"

    root = Path(os.getenv("PRIVATE_UPLOAD_DIR", ".local/uploads")).resolve()
    user_dir = (root / str(owner_id) / kind).resolve()
    if root not in user_dir.parents:
        raise RuntimeError("Private upload storage is misconfigured")
    user_dir.mkdir(parents=True, exist_ok=True)
    path = (user_dir / filename).resolve()
    if path.parent != user_dir:
        raise RuntimeError("Private upload storage is misconfigured")
    path.write_bytes(content)
    if os.name != "nt":
        os.chmod(user_dir.parent, 0o700)
        os.chmod(user_dir, 0o700)
        os.chmod(path, 0o600)
    return str(path)


async def read_private_image(reference: str, owner_id: int, kind: ImageKind) -> bytes:
    if reference.startswith("blob:"):
        pathname = _pathname(reference, owner_id, kind)
        from vercel import blob

        result = await blob.get_blob(pathname, access="private")
        return result.body
    return await asyncio.to_thread(_read_local_image, reference, owner_id, kind)


def _read_local_image(reference: str, owner_id: int, kind: ImageKind) -> bytes:
    path = _local_path(reference, owner_id, kind)
    if not path.is_file():
        raise FileNotFoundError("Private image not found")
    return path.read_bytes()


async def remove_private_image(reference: str) -> None:
    if reference.startswith("blob:"):
        if not _BLOB_REFERENCE.fullmatch(reference):
            raise FileNotFoundError("Private image not found")
        from vercel import blob

        await blob.delete_blob(reference.removeprefix("blob:"))
        return
    await asyncio.to_thread(remove_private_image_sync, reference)


def remove_private_image_sync(reference: str) -> None:
    if reference.startswith("blob:"):
        if not _BLOB_REFERENCE.fullmatch(reference):
            raise FileNotFoundError("Private image not found")
        from vercel.blob import sync as blob

        blob.delete_blob(reference.removeprefix("blob:"))
        return

    root = Path(os.getenv("PRIVATE_UPLOAD_DIR", ".local/uploads")).resolve()
    path = Path(reference).resolve()
    if root not in path.parents:
        raise FileNotFoundError("Private image not found")
    path.unlink(missing_ok=True)
