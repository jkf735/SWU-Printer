"""Download card images once and keep them on disk so they work offline."""

import os
from pathlib import Path

from swu_momir.data.cards import CACHE_PATH

IMAGE_FOLDER = CACHE_PATH.parent / "images"


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
