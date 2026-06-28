# Shared in-memory image fixtures for the EGI server test suite.
# TEST DATA — NOT REAL. Coordinates/metadata below are fake.

import io

from PIL import Image


def png_bytes(size=(50, 50), color=(120, 30, 30)):
    """A small in-memory PNG."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def jpeg_with_gps_bytes():
    """A JPEG carrying GPS + DateTime EXIF (fake coordinates)."""
    buf = io.BytesIO()
    img = Image.new("RGB", (60, 40), (10, 20, 30))
    exif = img.getexif()
    # GPS IFD: 1=LatRef 2=Lat 3=LonRef 4=Lon. Fake location.
    exif[0x8825] = {1: "N", 2: (40.0, 26.0, 46.12), 3: "W", 4: (79.0, 58.0, 55.64)}
    # DateTime (top-level) — round-trips reliably via Pillow.
    exif[0x0132] = "2026:01:02 03:04:05"
    img.save(buf, format="JPEG", exif=exif)
    buf.seek(0)
    return buf.getvalue()


def write_image_with_exif(path):
    """Write a small image carrying a fake EXIF ImageDescription to ``path``."""
    img = Image.new("RGB", (8, 8), color=(120, 30, 30))
    exif = img.getexif()
    exif[0x010E] = "secret location note"  # ImageDescription
    img.save(path, exif=exif)
