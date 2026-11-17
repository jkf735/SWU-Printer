"""The four knobs and two buttons, read with gpiozero.

Each knob step goes into the events queue as (Knob, +1 or -1), and each button press
as a state.Button. The player knob's push and the utility button are timed here, so
the queue only holds what the player meant: releasing a hold never also sends a push,
and a double-press never also sends single presses. gpiozero calls back on its own
threads, which is why events go through a queue.
"""

import os
import queue
import tempfile
import threading
import time

from swu_momir.state import Button, Knob

# BCM numbers (CLK, DT, SW). The README lists the header pins.
KNOB_PINS = {
    Knob.PLAYER: (17, 22, 23),
    Knob.COST: (5, 6, 13),
    Knob.ARENA: (20, 21, 12),
    Knob.KEYWORD: (19, 26, 16),
}
PRINT_PIN = 4
UTILITY_PIN = 3  # also wakes a halted Pi

# Knobs that count the wrong way. Listing them here is easier than swapping CLK and DT.
REVERSED: frozenset[Knob] = frozenset()

BOUNCE_SECONDS = 0.05
PRINT_COOLDOWN_SECONDS = 2.0  # Print presses this soon after the last one are ignored
HOLD_SECONDS = 1.0  # player knob push: enter setup
LONG_PRESS_SECONDS = 2.0  # utility: safe shutdown
DOUBLE_PRESS_SECONDS = 0.35  # a second utility press this soon makes a double-press


class Inputs:
    def __init__(self):
        # lgpio leaves small notification files in its working directory, which would
        # otherwise be the project folder.
        os.environ.setdefault("LG_WD", tempfile.gettempdir())
        from gpiozero import Button as GpioButton, RotaryEncoder  # Pi-only

        self.events: queue.Queue = queue.Queue()
        self._devices = []
        for knob, (clk, dt, _) in KNOB_PINS.items():
            step = -1 if knob in REVERSED else 1
            # wrap=True keeps the step count changing, so every detent sends an event.
            encoder = RotaryEncoder(clk, dt, wrap=True)
            encoder.when_rotated_clockwise = self._sender((knob, step))
            encoder.when_rotated_counter_clockwise = self._sender((knob, -step))
            self._devices.append(encoder)

        print_button = GpioButton(PRINT_PIN, bounce_time=BOUNCE_SECONDS)
        print_button.when_pressed = self._print_pressed
        self._last_print = None
        player_push = GpioButton(KNOB_PINS[Knob.PLAYER][2], bounce_time=BOUNCE_SECONDS,
                                 hold_time=HOLD_SECONDS)
        cost_push = GpioButton(KNOB_PINS[Knob.COST][2], bounce_time=BOUNCE_SECONDS)
        cost_push.when_pressed = self._sender(Button.COST_PUSH)
        utility = GpioButton(UTILITY_PIN, bounce_time=BOUNCE_SECONDS, hold_time=LONG_PRESS_SECONDS)
        self._devices += [print_button, player_push, cost_push, utility]
        self._player_push = _PlayerPush(player_push, self.events.put)
        self._utility = _Utility(utility, self.events.put)

    def _print_pressed(self):
        # Timed from the last press that counted, so mashing the button can't stretch the wait.
        now = time.monotonic()
        if self._last_print is None or now - self._last_print >= PRINT_COOLDOWN_SECONDS:
            self._last_print = now
            self.events.put(Button.PRINT)

    def _sender(self, event):
        def send():
            self.events.put(event)
        return send

    def close(self) -> None:
        self._utility.cancel()
        for device in self._devices:
            device.close()


class _PlayerPush:
    """A click sends a push when released. A hold sends a hold, and its release sends nothing."""

    def __init__(self, button, put):
        self._put = put
        self._held = False
        button.when_pressed = self._pressed
        button.when_held = self._on_held
        button.when_released = self._released

    def _pressed(self):
        self._held = False

    def _on_held(self):
        self._held = True
        self._put(Button.PLAYER_HOLD)

    def _released(self):
        if not self._held:
            self._put(Button.PLAYER_PUSH)


class _Utility:
    """Tells a press, a double-press and a long press apart.

    A single press is sent only once the double-press window passes with no second press.
    A long press is sent as soon as the hold time is reached, and its release sends nothing.
    """

    def __init__(self, button, put):
        self._put = put
        self._lock = threading.Lock()  # gpiozero and the timer call in from different threads
        self._timer = None  # running while waiting to see whether a second press follows
        self._second = False  # this press is the second of a double-press
        self._long = False  # this press already sent a long press
        button.when_pressed = self._pressed
        button.when_held = self._on_held
        button.when_released = self._released

    def _pressed(self):
        with self._lock:
            self._long = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
                self._second = True

    def _on_held(self):
        with self._lock:
            self._long = True
            self._second = False
            self._put(Button.UTILITY_LONG)

    def _released(self):
        with self._lock:
            if self._long:
                return
            if self._second:
                self._second = False
                self._put(Button.UTILITY_DOUBLE)
                return
            self._timer = threading.Timer(DOUBLE_PRESS_SECONDS, self._single)
            self._timer.daemon = True
            self._timer.start()

    def _single(self):
        with self._lock:
            if self._timer is not threading.current_thread():
                return  # a second press arrived just as the window closed
            self._timer = None
            self._put(Button.UTILITY)

    def cancel(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
