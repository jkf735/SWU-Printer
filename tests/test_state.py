import tempfile
import unittest
from pathlib import Path

from swu_momir.state import Button, Knob, Machine, Mode, PrintCard


def card(card_id, aspects=(), cost=0):
    return {"id": card_id, "printings": [card_id], "name": card_id, "aspects": list(aspects),
            "cost": cost, "arena": "Ground", "keywords": []}


UNITS = [card("LOF-254"), card("V", ["Vigilance"], cost=3), card("VV", ["Vigilance", "Vigilance"], cost=3)]
TOKENS = [card("Shield")]


class MachineTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "state.json"

    def machine(self):
        machine = Machine(UNITS, TOKENS, self.path)
        machine.turn(Knob.PLAYER, -1)  # from All, the startup position, to P1
        return machine

    def test_setup_changes_only_that_player_and_survives_a_restart(self):
        machine = self.machine()
        machine.press(Button.KEYWORD_HOLD)
        self.assertIs(machine.mode, Mode.SETUP)
        machine.press(Button.KEYWORD_PUSH)
        machine.press(Button.KEYWORD_PUSH)  # Vigilance is first on the cursor: now x2
        self.assertEqual(machine.display_rows()[2], "Pool 3")
        machine.press(Button.UTILITY)

        restarted = self.machine()
        self.assertEqual(restarted.identities["P1"].aspects, {"Vigilance": 2})
        self.assertEqual(restarted.identities["P2"].aspects, {})
        self.assertIn("Vigilance x2", restarted.lit_lights())

    def test_print_rolls_the_pool_and_reprint_survives_a_restart(self):
        machine = self.machine()
        machine.turn(Knob.COST, 3)  # no identity set, so nothing at cost 3 is in the pool
        self.assertEqual(machine.press(Button.PRINT), PrintCard(UNITS[0]))  # the Porg

        restarted = self.machine()
        self.assertEqual(restarted.press(Button.UTILITY), PrintCard(UNITS[0]))


if __name__ == "__main__":
    unittest.main()
