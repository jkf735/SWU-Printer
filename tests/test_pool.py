import unittest

from swu_momir.pool import ALL_MODE, Identity, eligible_units, roll


def unit(unit_id, aspects=(), cost=3):
    return {"id": unit_id, "printings": [unit_id], "aspects": list(aspects), "cost": cost,
            "arena": "Ground", "keywords": []}


class PoolTests(unittest.TestCase):
    def test_identity_must_cover_every_icon(self):
        units = [unit("double", ["Vigilance", "Vigilance"]), unit("single", ["Vigilance"]),
                 unit("mixed", ["Vigilance", "Heroism"]), unit("neutral")]

        def pool(identity):
            return [u["id"] for u in eligible_units(units, identity, 3)]

        self.assertEqual(pool(Identity({"Vigilance": 1, "Heroism": 1})), ["single", "mixed", "neutral"])
        self.assertEqual(pool(Identity({"Vigilance": 2}, neutral=False)), ["double", "single"])
        self.assertEqual(pool(ALL_MODE), ["double", "single", "mixed", "neutral"])

    def test_nine_means_nine_plus_and_an_empty_pool_rolls_the_porg(self):
        units = [unit("eight", cost=8), unit("nine", cost=9), unit("twelve", cost=12), unit("LOF-254", cost=0)]
        self.assertEqual([u["id"] for u in eligible_units(units, ALL_MODE, 9)], ["nine", "twelve"])
        self.assertEqual(roll(units, [])["id"], "LOF-254")


if __name__ == "__main__":
    unittest.main()
