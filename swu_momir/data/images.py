"""Where card images live on disk, so everything works offline.

Full-color originals in cache/images/ are only needed on the desktop. The Pi only
needs the finished 1-bit files in cache/prints/, made by tools/prepare_images.py.
"""

import os
from pathlib import Path

from swu_momir.data.cards import CACHE_PATH

IMAGE_FOLDER = CACHE_PATH.parent / "images"
PRINT_FOLDER = CACHE_PATH.parent / "prints"


def print_image_path(card: dict, folder: Path = PRINT_FOLDER) -> Path:
    """Return where a card's finished print image is kept."""
    return folder / f"{card['id']}.png"


def card_image_path(card: dict, folder: Path = IMAGE_FOLDER, timeout: float = 20) -> Path:
    """Return the path to a card's image, downloading it if it isn't on disk yet."""
    # Imported here because it loads slowly on the Pi and only downloads use it.
    import urllib.request

    path = folder / f"{card['id']}.png"
    if path.exists():
        return path

    folder.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    with urllib.request.urlopen(card["image_url"], timeout=timeout) as response:
        temp_path.write_bytes(response.read())
    os.replace(temp_path, path)
    return path
