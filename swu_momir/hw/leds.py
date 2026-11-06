"""The 11 aspect lights: a WS2811 pixel string on GPIO18.

Needs rpi_ws281x. The pixels keep their last colors for as long as they have power,
even after the Pi halts, so call off() before shutting down.
"""

import os
from collections.abc import Collection

PIN = 18  # GPIO18, header pin 12 (PWM0)
FREQUENCY = 800_000
DMA_CHANNEL = 10
PWM_CHANNEL = 0
BRIGHTNESS = 60  # out of 255

# Chain order: along the bottom row from the right end, then back across the top row.
# Names match Machine.lit_lights() in state.py.
LIGHTS = (
    ("Neutral", (120, 40, 5)),  # brown
    ("Villainy", (140, 0, 255)),  # purple
    ("Heroism", (255, 255, 255)),
    ("Cunning", (255, 200, 0)),
    ("Aggression", (255, 0, 0)),
    ("Command", (0, 255, 0)),
    ("Vigilance", (0, 80, 255)),
    ("Vigilance x2", (0, 80, 255)),
    ("Command x2", (0, 255, 0)),
    ("Aggression x2", (255, 0, 0)),
    ("Cunning x2", (255, 200, 0)),
)
OFF = (0, 0, 0)


class Leds:
    def __init__(self, brightness: int = BRIGHTNESS):
        # Without root, rpi_ws281x fails with a confusing "mailbox" error and then crashes.
        if os.geteuid() != 0:
            raise PermissionError("The LEDs need root. Run this with sudo.")
        from rpi_ws281x import PixelStrip, ws

        self._strip = PixelStrip(len(LIGHTS), PIN, FREQUENCY, DMA_CHANNEL, False, brightness,
                                 PWM_CHANNEL, ws.WS2811_STRIP_RGB)
        self._strip.begin()

    def show(self, lit: Collection[str], cursor: str | None = None, blink_on: bool = True) -> None:
        """Light the named lights. The cursor light is on only while blink_on is True,
        so flipping blink_on on a timer makes it blink."""
        for index, (name, color) in enumerate(LIGHTS):
            is_on = blink_on if name == cursor else name in lit
            self._strip.setPixelColorRGB(index, *(color if is_on else OFF))
        self._strip.show()

    def off(self) -> None:
        self.show(())
