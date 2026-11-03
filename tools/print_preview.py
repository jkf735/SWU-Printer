"""Render a few test cards the way the printer would, to check them on a desktop.

Run from the project folder with:  python -m tools.print_preview

Writes each card, a sheet of all of them, and a comparison of print styles to
cache/previews/. Screens show these far larger than the 48mm-wide prints.
"""

import time

from PIL import Image

from swu_momir.data.cards import CACHE_PATH, load_tokens, load_units
from swu_momir.data.images import card_image_path
from swu_momir.render import DEFAULT_STYLE, PRINT_WIDTH, PrintStyle, render_card

PREVIEW_FOLDER = CACHE_PATH.parent / "previews"
PREVIEW_IDS = (
    "LOF-254",  # Porg, the empty-pool joke
    "JTL-103",  # Chewbacca, the most rules text
    "LOF-117",  # Sifo-Dyas, also text-heavy
    "ASH-243",  # Darth Vader, dark art
    "LOF-089",  # Supremacy, a large Space unit
    "HMW-128",  # Mace Windu, a double aspect icon
    "TS26-T02",  # Clone Trooper, a token unit
    "ASH-T03",  # Shield, a token upgrade
)
COMPARED_ID = "JTL-103"
COMPARED_STYLES = (
    PrintStyle(),
    PrintStyle(dither=False),
    DEFAULT_STYLE,
    PrintStyle(black_point=DEFAULT_STYLE.black_point, white_point=DEFAULT_STYLE.white_point,
               sharpen=DEFAULT_STYLE.sharpen, dither=False),
)


def contact_sheet(images: list[Image.Image], columns: int, gap: int = 16) -> Image.Image:
    """Return images laid out in a grid on gray, for looking at previews side by side."""
    rows = [images[i:i + columns] for i in range(0, len(images), columns)]
    width = columns * PRINT_WIDTH + (columns + 1) * gap
    height = sum(max(image.height for image in row) + gap for row in rows) + gap
    sheet = Image.new("L", (width, height), 128)
    y = gap
    for row in rows:
        for column, image in enumerate(row):
            sheet.paste(image.convert("L"), (gap + column * (PRINT_WIDTH + gap), y))
        y += max(image.height for image in row) + gap
    return sheet


def main() -> None:
    PREVIEW_FOLDER.mkdir(parents=True, exist_ok=True)
    cards = {card["id"]: card for card in load_units() + load_tokens()}

    renders = []
    for card_id in PREVIEW_IDS:
        with Image.open(card_image_path(cards[card_id])) as source:
            start = time.perf_counter()
            image = render_card(source)
            elapsed = time.perf_counter() - start
        path = PREVIEW_FOLDER / f"{card_id}.png"
        image.save(path)
        renders.append(image)
        print(f"{card_id:9} {cards[card_id]['name']:16} {image.size} "
              f"{path.stat().st_size / 1000:.1f} KB, {elapsed * 1000:.0f} ms")
    contact_sheet(renders, columns=4).save(PREVIEW_FOLDER / "contact_sheet.png")

    with Image.open(card_image_path(cards[COMPARED_ID])) as source:
        compared = [render_card(source, style) for style in COMPARED_STYLES]
    contact_sheet(compared, columns=4).save(PREVIEW_FOLDER / "style_comparison.png")
    print(f"Saved to {PREVIEW_FOLDER}")


if __name__ == "__main__":
    main()
