"""Tableau selection of the graphical game's worlds (OLD difficulty)."""

import random
import unittest

from src.system.GameConfig import DIFFICULTY
from src.system.WorldManager import WorldManager


class WorldLevelPoolTests(unittest.TestCase):
    def draw(self, manager, count):
        ids = []
        for _ in range(count):
            ids.append(manager.get_next_level_id())
        return ids

    def test_first_loop_uses_normal_tableaux_and_later_loops_hard_ones(self):
        random.seed(0)
        manager = WorldManager(DIFFICULTY.OLD, None)
        self.assertFalse(manager.get_current_world().hard)  # normal sky
        first = self.draw(manager, 200)
        self.assertEqual(set(first), {1, 2, 3, 4, 5})
        manager.next_world()
        self.assertTrue(manager.get_current_world().hard)  # red sky, HARD tableaux
        later = self.draw(manager, 200)
        self.assertEqual(set(later), {5, 6, 7, 8, 9, 10})  # LEVEL5 and the five HARD tableaux
        for ids in (first, later):
            self.assertTrue(all(a != b for a, b in zip(ids, ids[1:])))


if __name__ == "__main__":
    unittest.main()
