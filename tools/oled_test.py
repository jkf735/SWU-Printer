"""OLED display test for the Pi, using the real display driver.

First draws a border around the whole screen. If it's cut off on any side, the display
isn't lined up with the driver. Then shows sample screens the way the game draws them.

Run from the project folder with:  .venv/bin/python -m tools.oled_test
It stops after 15 seconds, or sooner with Ctrl+C, and the screen blanks.
"""

import time

from PIL import ImageDraw

from swu_momir.hw.display import Display
from swu_momir.render import render_display

SAMPLES = (
    ("P1          Cost 5", "Space Sentinel", "Pool 42"),
    ("P2 Setup", "Aggression: 2", "Pool 318"),
    ("Tokens", "Clone Trooper", "3 of 13"),
)
BORDER_SECONDS = 3
SAMPLE_SECONDS = 4


def main() -> None:
    display = Display()
    try:
        border = render_display(("", "Edge check", ""))
        ImageDraw.Draw(border).rectangle((0, 0, border.width - 1, border.height - 1), outline=1)
        print("Border: all four edges should show.")
        display.show(border)
        time.sleep(BORDER_SECONDS)
        for rows in SAMPLES:
            print("Showing:", " / ".join(" ".join(row.split()) for row in rows))
            display.show(render_display(rows))
            time.sleep(SAMPLE_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        display.off()
        print("Screen off.")


if __name__ == "__main__":
    main()
