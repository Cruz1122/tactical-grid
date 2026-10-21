import copy
import json
import unittest
from math import isclose
from pathlib import Path

from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.astar import astar
from backend.algorithms.beam import beam_search
from backend.algorithms.bfs import bfs
from backend.algorithms.evaluation import evaluate
from backend.algorithms.minimax import minimax
from backend.algorithms.ucs import ucs
from backend.algorithms.verification import verify_path
from backend.game.engine import state_key
from backend.game.movement import legal_moves, move_cost
from backend.scenarios import prepare_scenario

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
FIXTURE_DIRS = (SCENARIOS / "busqueda", SCENARIOS / "adversarial")


def load(prefix: str) -> dict:
    path = next(
        path
        for directory in FIXTURE_DIRS
        for path in sorted(directory.glob(f"{prefix}*.json"))
    )
    source = json.loads(path.read_text(encoding="utf-8"))
    original = copy.deepcopy(source)
    state = prepare_scenario(source)
    if source != original:
        raise AssertionError(f"La carga mutó el fixture {path.name}")
    return state


def search_config(state: dict) -> tuple[str, dict[str, int]]:
    config = state["prueba"]
    return config["unidad_inicio"], config["objetivo"]


def annotated(result: dict, algorithm: str, unit_id: str, goal: dict) -> dict:
    value = copy.deepcopy(result)
    value.update(
        {"algorithm": algorithm, "unit_id": unit_id, "goal": copy.deepcopy(goal)}
    )
    return value


class FinalScenarioIntegrationTests(unittest.TestCase):
    def test_all_31_scenarios_load_without_mutating_their_json(self) -> None:
        paths = sorted(
            path
            for directory in FIXTURE_DIRS
            for path in directory.glob("[0-9][0-9]_*.json")
        )
        self.assertEqual(len(paths), 31)
        for path in paths:
            with self.subTest(scenario=path.name):
                source = json.loads(path.read_text(encoding="utf-8"))
                original = copy.deepcopy(source)
                state = prepare_scenario(source)
                self.assertEqual(source, original)
                self.assertEqual(len(state["unidades"]), 6)

    def test_case_02_matches_independent_movement_and_cost_oracles(self) -> None:
        state = load("02_")
        unit_id, goal = search_config(state)
        original = copy.deepcopy(state)

        breadth = bfs(state, unit_id, goal)
        cheapest = ucs(state, unit_id, goal)
        informed = astar(state, unit_id, goal, "second")

        self.assertEqual((breadth["moves"], breadth["cost"]), (10, 64.0))
        self.assertEqual((cheapest["moves"], cheapest["cost"]), (12, 12.0))
        self.assertEqual(informed["cost"], cheapest["cost"])
        for name, result in (
            ("bfs", breadth),
            ("ucs", cheapest),
            ("astar", informed),
        ):
            verification = verify_path(state, annotated(result, name, unit_id, goal))
            self.assertTrue(verification["valid"], verification)
        self.assertEqual(state, original)

    def test_case_05_exercises_real_beam_discarding(self) -> None:
        state = load("05_")
        unit_id, goal = search_config(state)
        results = {k: beam_search(state, unit_id, goal, k) for k in (1, 2, 4, 8)}

        self.assertFalse(results[1]["found"])
        for k in (2, 4, 8):
            self.assertTrue(results[k]["found"])
            self.assertLessEqual(results[k]["max_frontier"], k)
            self.assertGreater(results[k]["candidates_discarded"], 0)
            checked = verify_path(state, annotated(results[k], "beam", unit_id, goal))
            self.assertTrue(checked["valid"], checked)

    def test_exact_piece_geometry_and_fractional_cost_oracles(self) -> None:
        knight = load("11_")
        self.assertIn({"fila": 8, "columna": 7}, legal_moves(knight, "A_KN"))
        self.assertEqual(move_cost(knight, "A_KN", {"fila": 8, "columna": 7}), 1.0)

        rook = load("12_")
        self.assertEqual(move_cost(rook, "A_RO", {"fila": 5, "columna": 12}), 40.0)

        bishop = load("13_")
        unit_id, goal = search_config(bishop)
        self.assertFalse(bfs(bishop, unit_id, goal)["found"])
        self.assertFalse(ucs(bishop, unit_id, goal)["found"])

        fractional = load("20_")
        unit_id, goal = search_config(fractional)
        cheapest = ucs(fractional, unit_id, goal)
        informed = astar(fractional, unit_id, goal, "second")
        self.assertTrue(isclose(cheapest["cost"], 6.0))
        self.assertTrue(isclose(informed["cost"], 6.0))

    def test_state_key_and_evaluation_observe_composite_state(self) -> None:
        turn_a = load("06_estado_compuesto_turno_A")
        turn_b = load("06_estado_compuesto_turno_B")
        self.assertNotEqual(state_key(turn_a), state_key(turn_b))

        symmetric = load("21_")
        self.assertTrue(
            isclose(
                evaluate(symmetric, "A"),
                -evaluate(symmetric, "B"),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        )

    def test_real_adversarial_fixtures_match_at_depth_one(self) -> None:
        for prefix in ("07_", "08_", "09_", "10_"):
            state = load(prefix)
            for order in ("normal", "reverse"):
                with self.subTest(scenario=prefix, order=order):
                    plain = minimax(state, 1, order)
                    pruned = alpha_beta(state, 1, order)
                    self.assertEqual(plain["action"], pruned["action"])
                    self.assertEqual(plain["value"], pruned["value"])
                    self.assertEqual(plain["depth_reached"], 1)
                    self.assertEqual(pruned["depth_reached"], 1)


if __name__ == "__main__":
    unittest.main()
