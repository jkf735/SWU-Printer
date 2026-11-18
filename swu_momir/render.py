"""Turn card images into the 1-bit images the thermal printer prints, and the display's
text into frames for the OLED."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PRINT_WIDTH = 384  # the QR204 prints 384 dots across


@dataclass(frozen=True)
class PrintStyle:
    black_point: int = 0  # grays at or below this print solid black
    white_point: int = 255  # grays at or above this print as bare paper
    sharpen: int = 0  # unsharp mask strength, in percent
    dither: bool = True  # dither the mid-tones, or else cut them off at 50% gray


# The white point is low so tinted text boxes (gray 170-215) print as clean paper.
DEFAULT_STYLE = PrintStyle(black_point=30, white_point=150, sharpen=120)


def render_card(image: Image.Image, style: PrintStyle = DEFAULT_STYLE) -> Image.Image:
    """Return a card image as a 1-bit image exactly as wide as the printer."""
    if image.width > image.height:
        image = image.rotate(90, expand=True)

    # Flatten onto white first, because the card's rounded corners are transparent.
    image = image.convert("RGBA")
    flattened = Image.new("RGBA", image.size, "white")
    flattened.alpha_composite(image)

    height = round(image.height * PRINT_WIDTH / image.width)
    gray = flattened.convert("L").resize((PRINT_WIDTH, height), Image.Resampling.LANCZOS)

    if style.sharpen:
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=style.sharpen, threshold=0))
    span = max(style.white_point - style.black_point, 1)
    gray = gray.point(lambda value: max(0, min(255, (value - style.black_point) * 255 // span)))

    if style.dither:
        return gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    return gray.convert("1", dither=Image.Dither.NONE)


DISPLAY_SIZE = (128, 64)  # the OLED's pixels
# Largest first: a row that doesn't fit at one size is drawn at the next. Sizes 16 and 17
# are skipped because the built-in font's "i" loses its dot at them in 1-bit.
DISPLAY_FONT_SIZES = (18, 15, 13, 11)
DISPLAY_MARGIN = 2  # blank pixels kept at the left and right edges


@lru_cache(maxsize=None)
def display_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size)  # Pillow's built-in font, at any size (Pillow 10.1+)
    except (TypeError, ImportError, OSError):
        return ImageFont.load_default()  # a small fixed font, without FreeType


def render_display(rows: Sequence[str]) -> Image.Image:
    """Return the display's rows of text as a 1-bit image the size of the OLED.

    A run of two or more spaces in a row splits it: the text after it goes against the right
    edge, as in "P1          Cost 5".
    """
    width, height = DISPLAY_SIZE
    image = Image.new("1", DISPLAY_SIZE)
    draw = ImageDraw.Draw(image)
    band = height / len(rows)
    for index, row in enumerate(rows):
        parts = re.split(r" {2,}", row.strip(), maxsplit=1)
        for size in DISPLAY_FONT_SIZES:
            font = display_font(size)
            text_width = sum(draw.textlength(part, font=font) for part in parts)
            if text_width + 8 * (len(parts) - 1) <= width - 2 * DISPLAY_MARGIN:
                break
        middle = round(band * index + band / 2)
        draw.text((DISPLAY_MARGIN, middle), parts[0], fill=1, font=font, anchor="lm")
        if len(parts) > 1:
            draw.text((width - DISPLAY_MARGIN, middle), parts[1], fill=1, font=font, anchor="rm")
    return image
