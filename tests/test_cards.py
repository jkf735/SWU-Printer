import json
import tempfile
import unittest
from pathlib import Path

from swu_momir.data.cards import (
    TOKENS_URL,
    UpdateError,
    load_tokens,
    load_units,
    normalize_units,
    update_cards,
)


def raw_card(number="001", **overrides):
    card = {
        "Set": "SOR",
        "Number": number,
        "Name": f"Unit {number}",
        "Type": "Unit",
        "Aspects": ["Vigilance"],
        "Arenas": ["Ground"],
        "Cost": "3",
        "Power": "2",
        "HP": "4",
        "Unique": False,
        "FrontArt": f"https://example.test/{number}.png",
    }
    card.update(overrides)
    return card


def raw_token(number="T01"):
    return {"Set": "SOR", "Number": number, "Name": f"Token {number}", "Type": "Token Upgrade",
            "FrontArt": f"https://example.test/{number}.png"}


def response(*cards):
    return {"total_cards": len(cards), "data": list(cards)}


def many_units(count):
    return response(*(raw_card(f"{n:03}") for n in range(count)))


TOKENS = response(*(raw_token(f"T{n:02}") for n in range(10)))


class CardDataTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "cache" / "cards.json"
        self.corrections_path = Path(folder.name) / "corrections.json"
        self.corrections_path.write_text(json.dumps({"corrections": [
            {"card": "SOR-001", "add_keywords": ["Ambush"], "reason": "test"},
        ]}), encoding="utf-8")

    def update(self, units, tokens=TOKENS):
        return update_cards(self.path, fetch=lambda url: tokens if url == TOKENS_URL else units,
                            corrections_path=self.corrections_path)

    def test_reprints_merge_but_different_units_with_the_same_name_dont(self):
        result = normalize_units(response(
            raw_card("001", Name="Same"),
            raw_card("002", Name="Same", FrontText="Different wording."),
            raw_card("003", Name="Same", Cost="4"),
        ))
        self.assertEqual([card["printings"] for card in result.cards],
                         [["SOR-001", "SOR-002"], ["SOR-003"]])

    def test_saved_units_are_corrected_and_exclude_tokens(self):
        self.update(response(raw_card(), raw_card("T01", Type="Token Unit")))
        units = load_units(self.path)
        self.assertEqual([unit["id"] for unit in units], ["SOR-001"])
        self.assertEqual(units[0]["keywords"], ["Ambush"])
        self.assertEqual(len(load_tokens(self.path)), 10)

    def test_bad_updates_keep_the_cache(self):
        self.update(many_units(10))

        def fail_on_tokens(url):
            if url == TOKENS_URL:
                raise UpdateError("no network")
            return many_units(11)

        bad_fetches = {
            "failed download": fail_on_tokens,
            "empty": lambda url: TOKENS if url == TOKENS_URL else response(),
            "truncated": lambda url: TOKENS if url == TOKENS_URL else {"total_cards": 10, "data": []},
            "malformed": lambda url: {"error": "something went wrong"},
            "large drop": lambda url: TOKENS if url == TOKENS_URL else many_units(5),
        }
        for label, fetch in bad_fetches.items():
            with self.subTest(label), self.assertRaises(UpdateError):
                update_cards(self.path, fetch=fetch, corrections_path=self.corrections_path)
            self.assertEqual(len(load_units(self.path)), 10)


if __name__ == "__main__":
    unittest.main()
