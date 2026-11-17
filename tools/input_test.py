"""Knob and button test for the Pi, using the real input driver.

Prints each event the game would receive, with a running count per knob. The arena and
keyword knobs' pushes do nothing in the game, but they're shown too, to check their wiring.

Run from the project folder with:  .venv/bin/python -m tools.input_test
Stop with Ctrl+C.
"""

import os
import time

from swu_momir.hw.inputs import BOUNCE_SECONDS, KNOB_PINS, Inputs
from swu_momir.state import Button, Knob

DESCRIPTIONS = {
    Button.PRINT: "Print",
    Button.UTILITY: "Utility press",
    Button.UTILITY_DOUBLE: "Utility double-press",
    Button.UTILITY_LONG: "Utility long press (the game would shut down)",
    Button.PLAYER_PUSH: "Player push",
    Button.PLAYER_HOLD: "Player hold",
    Button.COST_PUSH: "Cost push",
}


def main() -> None:
    from gpiozero import Button as GpioButton

    inputs = Inputs()
    spare_pushes = []  # kept so the buttons aren't garbage-collected
    for knob, (_, _, sw) in KNOB_PINS.items():
        if knob in (Knob.ARENA, Knob.KEYWORD):
            push = GpioButton(sw, bounce_time=BOUNCE_SECONDS)
            push.when_pressed = lambda name=knob.name.title(): inputs.events.put(f"{name} push (unused)")
            spare_pushes.append(push)

    totals = dict.fromkeys(KNOB_PINS, 0)
    start = time.monotonic()
    print("Turn each knob and press each button. Each click of a knob should count exactly 1.")
    print("Ctrl+C stops.")
    try:
        while True:
            event = inputs.events.get()
            if isinstance(event, tuple):
                knob, step = event
                totals[knob] += step
                text = f"{knob.name.title():<8}{step:+d}   total {totals[knob]}"
            else:
                text = DESCRIPTIONS.get(event, event)
            print(f"{time.monotonic() - start:8.2f}s  {text}")
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        # Closing gpiozero's buttons can hang, so skip it: the pins are freed when the program ends.
        os._exit(0)


if __name__ == "__main__":
    main()
