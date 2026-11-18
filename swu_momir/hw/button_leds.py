"""The LEDs in the Print and Utility buttons, each lit through a 74AHCT14 inverter.

A high pin lights its LED. GPIO 2 has an onboard pull-up, so the Utility LED is lit
whenever no program holds the pin: while the Pi boots, after this program ends, and
while the Pi is halted, which is when pressing Utility wakes it. GPIO 27 defaults low,
so the Print LED stays dark at those times.
"""

import os
import tempfile
from collections.abc import Collection

PINS = {"Print": 27, "Utility": 2}  # BCM numbers; header pins 13 and 3
BRIGHTNESS = 1.0  # 0 to 1. Below 1 dims with software PWM, which showed no flicker.


class ButtonLeds:
    def __init__(self, brightness: float = BRIGHTNESS):
        os.environ.setdefault("LG_WD", tempfile.gettempdir())  # see hw/inputs.py
        from gpiozero import PWMLED  # Pi-only

        self._brightness = brightness
        self._leds = {name: PWMLED(pin) for name, pin in PINS.items()}

    def show(self, lit: Collection[str]) -> None:
        """Light the named buttons, "Print" and "Utility", and turn the other off."""
        for name, led in self._leds.items():
            led.value = self._brightness if name in lit else 0
