from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from backend.app import private_storage


@pytest.mark.anyio
async def test_local_private_image_round_trip_is_scoped_to_owner_and_kind(tmp_path, monkeypatch):
    monkeypatch.delenv("BLOB_STORE_ID",raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN",raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN",raising=False)
    monkeypatch.setenv("PRIVATE_UPLOAD_DIR",str(tmp_path))

    reference=await private_storage.store_private_image(7,"food",b"jpeg bytes")
    assert Path(reference).parent == tmp_path.resolve() / "7" / "food"
    assert await private_storage.read_private_image(reference,7,"food")==b"jpeg bytes"
    with pytest.raises(FileNotFoundError):
        await private_storage.read_private_image(reference, 8, "food")
    with pytest.raises(FileNotFoundError):
        await private_storage.read_private_image(reference, 7, "scan")
    private_storage.remove_private_image_sync(reference)
    with pytest.raises(FileNotFoundError):
        await private_storage.read_private_image(reference,7,"food")


@pytest.mark.anyio
async def test_private_blob_round_trip_uses_owner_scoped_path_and_private_access(monkeypatch):
    monkeypatch.setenv("BLOB_STORE_ID","store_lossfit")
    calls=[]
    async def put(pathname,body,**kwargs):
        calls.append(("put",pathname,kwargs))
        return SimpleNamespace(pathname=pathname)
    async def get(pathname,**kwargs):
        calls.append(("get",pathname,kwargs))
        return SimpleNamespace(body=b"private jpeg")
    async def remove(pathname):
        calls.append(("delete",pathname,{}))

    parent=ModuleType("vercel");blob=ModuleType("vercel.blob");sync=ModuleType("vercel.blob.sync")
    blob.put_blob=put;blob.get_blob=get;blob.delete_blob=remove;blob.sync=sync
    sync.delete_blob=lambda pathname:calls.append(("delete-sync",pathname,{}))
    parent.blob=blob
    monkeypatch.setitem(sys.modules,"vercel",parent)
    monkeypatch.setitem(sys.modules,"vercel.blob",blob)
    monkeypatch.setitem(sys.modules,"vercel.blob.sync",sync)

    reference=await private_storage.store_private_image(19,"scan",b"image")
    assert reference.startswith("blob:users/19/scan/")
    assert await private_storage.read_private_image(reference,19,"scan")==b"private jpeg"
    await private_storage.remove_private_image(reference)
    private_storage.remove_private_image_sync(reference)
    assert calls[0][2]["access"]=="private"
    assert calls[1][2]["access"]=="private"
    assert [call[0] for call in calls]==["put","get","delete","delete-sync"]


@pytest.mark.anyio
async def test_blob_reference_rejects_another_owner_and_invalid_path_before_read(monkeypatch):
    monkeypatch.setenv("BLOB_STORE_ID","store_lossfit")
    reference="blob:users/19/scan/"+"a"*32+".jpg"
    with pytest.raises(FileNotFoundError):
        await private_storage.read_private_image(reference,20,"scan")
    with pytest.raises(FileNotFoundError):
        await private_storage.read_private_image(reference,19,"food")
    with pytest.raises(FileNotFoundError):
        private_storage.remove_private_image_sync("blob:users/19/scan/../secret.jpg")
