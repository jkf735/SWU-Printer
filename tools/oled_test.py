"""OLED display test for the Pi.

Draws a border around the whole screen and three rows of sample text, the way
the game's display will look. If the border is cut off on any side, the
display isn't lined up with the driver.

Run from the project folder with:  .venv/bin/python -m tools.oled_test
It stops after 15 seconds, or sooner with Ctrl+C, and the screen blanks.
"""

import time

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import ssd1309

SHOW_SECONDS = 15


def main() -> None:
    # luma's default pins are DC = GPIO 24 and RST = GPIO 25, which match the wiring.
    device = ssd1309(spi(port=0, device=0))
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white")
        draw.text((3, 2), "P1          Cost 5", fill="white")
        draw.text((3, 24), "Space  Sentinel", fill="white")
        draw.text((3, 46), "Pool 42", fill="white")
    print(f"Showing a border and three rows of text for {SHOW_SECONDS} seconds. Ctrl+C stops it sooner.")
    try:
        time.sleep(SHOW_SECONDS)
    except KeyboardInterrupt:
        pass
    print("Screen off.")


if __name__ == "__main__":
    main()
