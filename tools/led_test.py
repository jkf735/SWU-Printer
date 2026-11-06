"""Aspect-light test for the Pi, using the real light driver.

Lights each aspect in chain order, then blinks a setup cursor on Vigilance.

Run from the project folder with:  sudo .venv/bin/python -m tools.led_test
Stop with Ctrl+C (the lights turn off).
"""

import time

from swu_momir.hw.leds import LIGHTS, Leds


def main() -> None:
    leds = Leds()
    names = [name for name, _ in LIGHTS]
    try:
        while True:
            for index, name in enumerate(names):
                print(f"pixel {index}: {name}")
                leds.show(names[:index + 1])
                time.sleep(0.4)
            time.sleep(2)

            print("Setup cursor blinking on Vigilance, with Heroism and Neutral set")
            for blink in range(8):
                leds.show({"Heroism", "Neutral"}, cursor="Vigilance", blink_on=blink % 2 == 0)
                time.sleep(0.4)
    except KeyboardInterrupt:
        pass
    finally:
        leds.off()
        print("Lights off.")


if __name__ == "__main__":
    main()
