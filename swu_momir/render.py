"""Turn card images into the 1-bit images the thermal printer prints."""

from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps

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
