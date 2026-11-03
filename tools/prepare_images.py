"""Download every unit and token image and render it to a finished print file.

Run from the project folder with:  python -m tools.prepare_images

Cards that already have a print file are skipped, so this is quick to re-run after
a card update, and running it again retries any that failed. After changing the
print style, add --rerender to redo them all from the saved originals.

Copy cache/cards.json and cache/prints/ to the Pi. It doesn't need cache/images/.
"""

import http.client
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

from swu_momir.data.cards import load_tokens, load_units
from swu_momir.data.images import card_image_path, print_image_path
from swu_momir.render import render_card

WORKERS = 4  # enough to be quick without hammering the image server
PROGRESS_EVERY = 200


def prepare_card(card: dict, rerender: bool) -> bool:
    """Make a card's print file. Returns False if it already had one and was skipped."""
    path = print_image_path(card)
    if path.exists() and not rerender:
        return False

    with Image.open(card_image_path(card)) as source:
        image = render_card(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    image.save(temp_path, format="PNG")
    os.replace(temp_path, path)
    return True


def main() -> int:
    rerender = "--rerender" in sys.argv[1:]
    cards = load_units() + load_tokens()
    rendered = skipped = 0
    failed = []

    with ThreadPoolExecutor(WORKERS) as pool:
        jobs = {pool.submit(prepare_card, card, rerender): card for card in cards}
        for done, job in enumerate(as_completed(jobs), start=1):
            card = jobs[job]
            try:
                if job.result():
                    rendered += 1
                else:
                    skipped += 1
            except (OSError, ValueError, http.client.HTTPException) as error:
                failed.append(f"{card['id']} {card['name']}: {error}")
            if done % PROGRESS_EVERY == 0:
                print(f"{done} of {len(cards)}", flush=True)

    print(f"Rendered {rendered}, skipped {skipped}, failed {len(failed)}")
    for note in failed:
        print(f"  failed: {note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
