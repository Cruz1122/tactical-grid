"""Pruebas de regresión para distancias topológicas y partidas adversariales reales."""

import copy
import json
import unittest
from pathlib import Path

from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.evaluation import _movement_distance, evaluate
from backend.algorithms.minimax import minimax
from backend.game.engine import check_winner, transition
from backend.scenarios import prepare_scenario

ROOT = Path(__file__).resolve().parents[2]


def scenario(relative):
    return prepare_scenario(json.loads((ROOT / relative).read_text(encoding="utf-8")))


class AdversarialAutoplayRegressions(unittest.TestCase):
    def test_maze_distance_respects_detours(self):
        state = scenario("scenarios/partida/mapa_partida_presentacion.json")
        unit = next(u for u in state["unidades"] if u["id"] == "A1")
        queen = (2, 3)
        manhattan = abs(unit["fila"] - queen[0]) + abs(unit["columna"] - queen[1])
        self.assertGreater(_movement_distance(state, unit, queen), manhattan)
        neighbor = copy.deepcopy(state)
        moved = next(u for u in neighbor["unidades"] if u["id"] == "A1")
        moved["fila"], moved["columna"] = 0, 0
        self.assertLess(_movement_distance(neighbor, moved, queen), _movement_distance(state, unit, queen))

    def test_ally_unblocks_carrier_route(self):
        state = scenario("scenarios/adversarial/externo_adversarial_3v3.json")
        carrier = next(u for u in state["unidades"] if u["id"] == "B3")
        carrier["fila"], carrier["columna"] = 17, 19
        base = (19, 19)
        blocked = _movement_distance(state, carrier, base, block_allies=True)
        teammate = next(u for u in state["unidades"] if u["id"] == "B2")
        teammate["fila"], teammate["columna"] = 18, 17
        opened = _movement_distance(state, carrier, base, block_allies=True)
        self.assertGreater(blocked, opened)
        self.assertEqual(opened, 2)

    def test_small_game_reaches_real_victory(self):
        for method in (minimax, alpha_beta):
            with self.subTest(algorithm=method.__name__):
                state = scenario("scenarios/partida/mapa_partida_presentacion.json")
                for _ in range(35):
                    if check_winner(state) is not None:
                        break
                    before = copy.deepcopy(state)
                    result = method(state, 2)
                    self.assertEqual(before, state)
                    self.assertIsNotNone(result["action"])
                    state = transition(state, result["action"])
                self.assertIn(check_winner(state), ("A", "B"))
                self.assertEqual(state["juego"]["estado"], "finalizado")

    def test_large_game_adversarial_action_is_legal_and_immutable(self):
        state = scenario("scenarios/adversarial/externo_adversarial_3v3.json")
        original = copy.deepcopy(state)
        for method in (minimax, alpha_beta):
            result = method(state, 2)
            self.assertIsNotNone(result["action"])
            next_state = transition(state, result["action"])
            self.assertEqual(next_state["turno"], "B")
            self.assertEqual(state, original)
        self.assertEqual(evaluate(state, "A"), -evaluate(state, "B"))

if __name__ == "__main__":
    unittest.main()