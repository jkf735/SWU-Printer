"""Play through the machine's controls with no hardware, on a desktop or the Pi.

Run from the project folder with:  python -m tools.sim  (python3 on the Pi)

To also show the aspect lights on the real LEDs, run it on the Pi with:
    sudo .venv/bin/python -m tools.sim --lights

Printed cards are saved to cache/last_print.png, so keep that open in an editor
tab to see them. Over SSH on the Pi, the status line names the card instead.
Identities and the last card are saved to cache/state.json, as they would be on
the Pi.
"""

import os
import shutil
import sys
import threading

from swu_momir.data.cards import CACHE_PATH, load_tokens, load_units
from swu_momir.data.images import print_image_path
from swu_momir.state import (COLORS, SETUP_CURSOR, STATE_PATH, Button, Knob, Machine, PrintCard,
                             ShutDown)

LAST_PRINT_PATH = CACHE_PATH.with_name("last_print.png")
QUIT_KEYS = ("\x1b", "\x03")  # Esc and Ctrl-C
BLINK_SECONDS = 0.4

TURNS = {
    "q": (Knob.PLAYER, -1), "w": (Knob.PLAYER, 1),
    "e": (Knob.COST, -1), "r": (Knob.COST, 1),
    "t": (Knob.ARENA, -1), "y": (Knob.ARENA, 1),
    "u": (Knob.KEYWORD, -1), "i": (Knob.KEYWORD, 1),
}
PRESSES = {
    "o": Button.KEYWORD_PUSH,
    "p": Button.KEYWORD_HOLD,
    " ": Button.PRINT,
    "z": Button.UTILITY,
    "x": Button.UTILITY_DOUBLE,
    "c": Button.UTILITY_LONG,
}
LEGEND = """\
Knobs (left, right):  Player q w   Cost e r   Arena t y   Keyword u i
Keyword knob:         o push   p hold
Buttons:              Space Print   z Utility   x double-press   c long-press
Esc quits"""


def read_keys():
    """Yield one key at a time: instantly in a terminal, otherwise from piped text."""
    if not sys.stdin.isatty():
        yield from sys.stdin.read().replace("\n", "")
    elif os.name == "nt":
        yield from read_windows_keys()
    else:
        yield from read_linux_keys()


def read_windows_keys():
    import msvcrt

    while True:
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):  # the first half of an arrow or function key
            msvcrt.getwch()
            continue
        yield key


def read_linux_keys():
    import termios
    import tty

    stdin = sys.stdin.fileno()
    saved_settings = termios.tcgetattr(stdin)
    tty.setcbreak(stdin)  # send keys right away, without waiting for Enter or echoing them
    try:
        while True:
            keys = os.read(stdin, 32).decode(errors="ignore")
            if keys.startswith("\x1b") and len(keys) > 1:  # an arrow or function key, not Esc
                continue
            yield from keys
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(stdin, termios.TCSADRAIN, saved_settings)


class Lights:
    """Mirrors the machine on the real aspect lights, blinking the setup cursor."""

    def __init__(self, machine: Machine):
        from swu_momir.hw.leds import Leds  # Pi-only

        self.machine = machine
        self.leds = Leds()
        self.lock = threading.Lock()  # the blink thread and the key loop both update the lights
        self.blink_on = True
        self.stopped = threading.Event()
        threading.Thread(target=self._blink, daemon=True).start()

    def update(self) -> None:
        with self.lock:
            if not self.stopped.is_set():
                self.leds.show(self.machine.lit_lights(), self.machine.cursor, self.blink_on)

    def _blink(self) -> None:
        while not self.stopped.wait(BLINK_SECONDS):
            self.blink_on = not self.blink_on
            if self.machine.cursor:
                self.update()

    def off(self) -> None:
        self.stopped.set()
        with self.lock:
            self.leds.off()


def light(machine: Machine, name: str, label: str) -> str:
    """Return one light as text: [Vig] is lit, >Vig< is the setup cursor, and vig is dark."""
    is_lit = name in machine.lit_lights()
    if name == machine.cursor:
        return f">{label if is_lit else label.lower()}<"
    return f"[{label}]" if is_lit else f" {label.lower()} "


def frame(machine: Machine, status: str) -> str:
    """Return the whole front panel as text."""
    top_row = " ".join(light(machine, f"{color} x2", color[:3]) for color in COLORS)
    bottom_row = " ".join(light(machine, name, name[:3]) for name in SETUP_CURSOR)
    display = [f"| {row:<22} |" for row in machine.display_rows()]
    border = "+" + "-" * 24 + "+"
    return "\n".join([f"x2  {top_row}", f"    {bottom_row}", "", border, *display, border, "",
                      status, "", LEGEND])


def describe(card: dict) -> str:
    title = f"{card['name']}, {card['subtitle']}" if card.get("subtitle") else card["name"]
    if "cost" in card:
        details = f"cost {card['cost']}, {card['arena']}, {', '.join(card['aspects']) or 'no aspects'}"
    else:
        details = card["type"]
    return f"{title} ({card['id']}): {details}"


def show_print(card: dict) -> str:
    """Save the card's print file where it can be viewed, and return a status line."""
    source = print_image_path(card)
    temp_path = LAST_PRINT_PATH.with_name(LAST_PRINT_PATH.name + ".tmp")
    try:
        shutil.copyfile(source, temp_path)
        os.replace(temp_path, LAST_PRINT_PATH)
    except OSError as error:
        return f"Printed {describe(card)}, but could not show it ({error}). Try: python -m tools.prepare_images"
    return f"Printed {describe(card)}"


def main(state_path=STATE_PATH) -> None:
    machine = Machine(load_units(), load_tokens(), state_path)
    lights = Lights(machine) if "--lights" in sys.argv[1:] else None
    interactive = sys.stdin.isatty()
    if interactive and os.name == "nt":
        os.system("")  # lets the Windows console understand the clear-screen code below

    def draw(status: str) -> None:
        print(("\x1b[2J\x1b[H" if interactive else "\n") + frame(machine, status), flush=True)
        if lights:
            lights.update()

    try:
        draw(f"Printed cards are saved to {LAST_PRINT_PATH}")
        for key in read_keys():
            if key in QUIT_KEYS:
                break
            key = key.lower()
            status = ""
            if key in TURNS:
                machine.turn(*TURNS[key])
            elif key in PRESSES:
                result = machine.press(PRESSES[key])
                if isinstance(result, PrintCard):
                    status = show_print(result.card)
                elif isinstance(result, ShutDown):
                    draw("The Pi would shut down now. Run the sim again to wake it.")
                    break
            draw(status)
    finally:
        if lights:
            lights.off()


if __name__ == "__main__":
    main()
