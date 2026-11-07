"""Garden plant thumbnails, and the upload checks shared with /plants/identify."""

from io import BytesIO

from PIL import Image

from app.images import InvalidImage, to_jpeg
from tests.helpers import image_bytes


def add_plant(client, catalog) -> int:
    return client.post("/garden", json={"plant_id": catalog["Rosa"].id}).json()["id"]


def upload(client, gid, data, name="leaf.png", mime="image/png"):
    return client.put(f"/garden/{gid}/photo", files={"photo": (name, data, mime)})


def test_put_then_get_returns_a_small_jpeg(client, catalog):
    gid = add_plant(client, catalog)
    assert upload(client, gid, image_bytes("PNG", (2000, 1000))).status_code == 204
    r = client.get(f"/garden/{gid}/photo")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    image = Image.open(BytesIO(r.content))
    assert (image.format, max(image.size)) == ("JPEG", 512)
    assert client.get(f"/garden/{gid}").json()["has_photo"] is True
    assert client.get("/garden").json()[0]["has_photo"] is True


def test_a_second_upload_replaces_the_photo(client, catalog):
    gid = add_plant(client, catalog)
    upload(client, gid, image_bytes("PNG", (100, 100)))
    upload(client, gid, image_bytes("WEBP", (300, 150)), "b.webp", "image/webp")
    image = Image.open(BytesIO(client.get(f"/garden/{gid}/photo").content))
    assert image.size == (300, 150)


def test_bad_uploads_are_422_in_the_usual_shape(client, catalog):
    gid = add_plant(client, catalog)
    for data, name in (
        (b"", "empty.png"),
        (b"not an image at all", "fake.png"),
        (image_bytes("GIF"), "anim.gif"),  # decodes, but not an allowed format
        (b"x" * (5 * 1024 * 1024 + 1), "huge.png"),
    ):
        r = upload(client, gid, data, name)
        assert r.status_code == 422, name
        [problem] = r.json()["detail"]
        assert problem["loc"] == ["body", "photo"]
    assert client.get(f"/garden/{gid}/photo").status_code == 404  # nothing stored


def test_photo_for_missing_garden_plant_is_404(client):
    assert upload(client, 999, image_bytes()).status_code == 404


def test_deleting_the_plant_deletes_its_photo(client, session, catalog):
    gid = add_plant(client, catalog)
    upload(client, gid, image_bytes())
    assert client.delete(f"/garden/{gid}").status_code == 204
    from app.models import GardenPhoto

    assert session.get(GardenPhoto, gid) is None


def test_to_jpeg_strips_metadata_and_rejects_bombs():
    exif = Image.Exif()
    exif[0x010F] = "Camera maker"
    out = BytesIO()
    Image.new("RGB", (10, 10)).save(out, format="JPEG", exif=exif)
    cleaned = Image.open(BytesIO(to_jpeg(out.getvalue(), 512)))
    assert not cleaned.getexif()  # no location or camera data is kept

    bomb = BytesIO()
    Image.new("1", (10_000, 10_000)).save(bomb, format="PNG")  # 100 M pixels
    try:
        to_jpeg(bomb.getvalue(), 512)
    except InvalidImage:
        pass
    else:
        raise AssertionError("a decompression bomb was accepted")
