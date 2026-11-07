"""Uploaded photos are untrusted input: check them, then re-encode as JPEG."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
IDENTIFY_MAX_SIDE = 1024  # enough detail for the model, far fewer tokens
THUMBNAIL_MAX_SIDE = 512
Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs


class InvalidImage(ValueError):
    """str(error) is a sentence you can show to a user."""


def to_jpeg(data: bytes, max_side: int) -> bytes:
    """Decode, fix rotation, strip metadata, shrink to max_side and re-encode."""
    if not data:
        raise InvalidImage("The photo is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImage("The photo is larger than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            if image.format not in ALLOWED_FORMATS:
                raise InvalidImage("Use a JPEG, PNG or WebP photo.")
            image.load()
    except InvalidImage:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidImage("The file is not a readable photo.") from exc
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((max_side, max_side))
    out = BytesIO()
    image.save(out, format="JPEG", quality=85)  # no EXIF: location data is dropped
    return out.getvalue()
