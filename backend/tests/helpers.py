"""Small helpers shared by the tests."""

from io import BytesIO

from PIL import Image


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 48)) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, (40, 160, 60)).save(out, format=fmt)
    return out.getvalue()
