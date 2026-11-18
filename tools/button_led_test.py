"""Button LED test for the Pi (an experiment: the button LEDs aren't part of the game yet).

Each LED runs from 5V through one of the 74AHCT14's spare inverters, so a high pin lights it:
    Print LED:    GPIO 27 (pin 13) -> 74AHCT14 pin 9;  74AHCT14 pin 8 -> LED -;  LED + (grey) -> 5V rail
    Utility LED:  GPIO 2 (pin 3)   -> 74AHCT14 pin 5;  74AHCT14 pin 6 -> LED -;  LED + (white) -> 5V rail

Lights each LED at full brightness, then steps it down, dimming with software PWM.
Watch for flicker at the low levels.

Run from the project folder with:  .venv/bin/python -m tools.button_led_test
Stop sooner with Ctrl+C.
"""

import time

from gpiozero import PWMLED

PRINT_PIN = 27
UTILITY_PIN = 2
LEVELS = (1.0, 0.5, 0.2, 0.05)  # fraction of full brightness
STEP_SECONDS = 1.5


def main() -> None:
    leds = {"Print": PWMLED(PRINT_PIN), "Utility": PWMLED(UTILITY_PIN)}
    try:
        for name, led in leds.items():
            for level in LEVELS:
                print(f"{name} at {level:.0%}")
                led.value = level
                time.sleep(STEP_SECONDS)
            led.off()
            time.sleep(0.5)
        print("Both blinking")
        for led in leds.values():
            led.blink(on_time=0.4, off_time=0.4)
        time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        for led in leds.values():
            led.off()
        print("Done.")


if __name__ == "__main__":
    main()
