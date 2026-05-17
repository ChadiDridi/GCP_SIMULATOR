import pytest


@pytest.mark.asyncio
async def test_list_buckets_empty(client):
    resp = await client.get("/storage/v1/b?project=local-dev")
    assert resp.status_code == 200
    assert resp.json()["kind"] == "storage#buckets"


@pytest.mark.asyncio
async def test_create_and_get_bucket(client):
    resp = await client.post("/storage/v1/b", json={"name": "test-bucket"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "test-bucket"

    resp = await client.get("/storage/v1/b/test-bucket")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_upload_and_download_object(client):
    await client.post("/storage/v1/b", json={"name": "upload-test"})

    resp = await client.post(
        "/upload/storage/v1/b/upload-test/o?uploadType=media&name=hello.txt",
        content=b"Hello, GCS!",
        headers={"Content-Type": "text/plain"},
    )
    assert resp.status_code == 200

    resp = await client.get("/storage/v1/b/upload-test/o/hello.txt?alt=media")
    assert resp.status_code == 200
    assert resp.content == b"Hello, GCS!"
