import copy
import json
import math
import random
import unittest
from typing import Any

from backend.algorithms.astar import astar
from backend.algorithms.beam import beam_search
from backend.algorithms.evaluation import evaluate
from backend.algorithms.ucs import ucs
from backend.game.engine import action_successors, state_key, transition
from backend.game.validation import validate_state
from backend.scenarios import prepare_scenario


def generated_case(seed: int) -> tuple[dict[str, Any], dict[str, int]]:
    randomizer = random.Random(seed)
    rows = randomizer.randint(6, 8)
    columns = randomizer.randint(7, 9)
    protected = {
        *((0, column) for column in range(columns)),
        *((row, columns - 1) for row in range(rows)),
        (1, 0), (2, 0), (3, 0),
        (rows - 2, columns - 1),
        (rows - 3, columns - 1),
        (rows - 4, columns - 1),
    }
    resource = (rows // 2, columns // 2)
    protected.add(resource)
    kings: dict[str, list[dict[str, Any]]] | None = None
    if seed % 2:
        king_a = (rows - 1, 1)
        king_b = (rows - 1, columns - 2)
        protected.update((king_a, king_b))
        kings = {
            "A": [{"id": "KA", "fila": king_a[0], "columna": king_a[1]}],
            "B": [{"id": "KB", "fila": king_b[0], "columna": king_b[1]}],
        }

    terrain: list[list[str]] = []
    for row in range(rows):
        terrain_row = []
        for column in range(columns):
            position = (row, column)
            if position not in protected and randomizer.random() < 0.12:
                terrain_row.append("muro")
            else:
                terrain_row.append(randomizer.choice(("camino", "pasto", "barato")))
        terrain.append(terrain_row)

    occupied = set(protected)
    goal_candidates = [
        (row, column)
        for row in range(rows)
        for column in range(columns)
        if terrain[row][column] != "muro" and (row, column) not in occupied
    ]
    goal_row, goal_column = randomizer.choice(goal_candidates)
    scenario: dict[str, Any] = {
        "version": "1.0",
        "mapa": {"filas": rows, "columnas": columns},
        "tipos_terreno": {
            "camino": {"costo": randomizer.randint(1, 3), "transitable": True},
            "pasto": {"costo": randomizer.randint(4, 8), "transitable": True},
            "barato": {"costo": randomizer.choice((0.25, 0.5, 0.75)), "transitable": True},
            "muro": {"transitable": False},
        },
        "terreno": terrain,
        "bases": {
            "A": {"fila": 0, "columna": 0},
            "B": {"fila": rows - 1, "columna": columns - 1},
        },
        "recurso": {"fila": resource[0], "columna": resource[1]},
        "unidades": [
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 0},
            {"id": "A2", "bando": "A", "tipo": "rook", "fila": 2, "columna": 0},
            {"id": "A3", "bando": "A", "tipo": "bishop", "fila": 3, "columna": 0},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": rows - 2, "columna": columns - 1},
            {"id": "B2", "bando": "B", "tipo": "knight", "fila": rows - 3, "columna": columns - 1},
            {"id": "B3", "bando": "B", "tipo": "rook", "fila": rows - 4, "columna": columns - 1},
        ],
        "turno": "A",
        "juego": {"portador_recurso": None},
        "prueba": {
            "modo": "busqueda",
            "unidad_inicio": "A1",
            "objetivo": {"fila": goal_row, "columna": goal_column},
        },
        "semilla": seed,
    }
    if kings is not None:
        scenario["reyes"] = kings
    return prepare_scenario(scenario), {"fila": goal_row, "columna": goal_column}


def transpose_scenario(state: dict[str, Any], goal: dict[str, int]) -> tuple[dict, dict]:
    value = copy.deepcopy(state)
    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]
    value["mapa"] = {"filas": columns, "columnas": rows}
    value["terreno"] = [
        [state["terreno"][row][column] for row in range(rows)]
        for column in range(columns)
    ]

    def swap(position: dict[str, int]) -> None:
        position["fila"], position["columna"] = position["columna"], position["fila"]

    for base in value["bases"].values():
        swap(base)
    if value.get("recurso") is not None:
        swap(value["recurso"])
    if value.get("recurso_spawn") is not None:
        swap(value["recurso_spawn"])
    for unit in value["unidades"]:
        swap(unit)
        swap(unit["spawn"])
    for group in value.get("reyes", {}).values():
        for king in group:
            swap(king)
    transposed_goal = {"fila": goal["columna"], "columna": goal["fila"]}
    value["prueba"]["objetivo"] = copy.deepcopy(transposed_goal)
    validate_state(value)
    return value, transposed_goal


class GeneratedPropertyTests(unittest.TestCase):
    maxDiff = None

    def test_seeds_0_to_99_preserve_search_and_metamorphic_properties(self) -> None:
        for seed in range(100):
            with self.subTest(seed=seed):
                state, goal = generated_case(seed)
                original = copy.deepcopy(state)
                optimal = ucs(state, "A1", goal)
                informed = astar(state, "A1", goal, "second")

                self.assertEqual(optimal["found"], informed["found"], json.dumps(state, ensure_ascii=False))
                if optimal["found"]:
                    self.assertTrue(math.isclose(
                        optimal["cost"], informed["cost"],
                        rel_tol=1e-9, abs_tol=1e-9,
                    ))
                self.assertEqual(state, original)
                for result in (optimal, informed):
                    self.assertGreaterEqual(result["states_generated"], 1)
                    self.assertGreaterEqual(result["states_expanded"], 0)
                    self.assertGreaterEqual(result["max_frontier"], 1)

                factor = (seed % 5) + 1
                scaled = copy.deepcopy(state)
                for definition in scaled["tipos_terreno"].values():
                    if definition.get("transitable") is True:
                        definition["costo"] *= factor
                scaled_result = ucs(scaled, "A1", goal)
                self.assertEqual(scaled_result["found"], optimal["found"])
                if optimal["found"]:
                    self.assertTrue(math.isclose(
                        scaled_result["cost"], optimal["cost"] * factor,
                        rel_tol=1e-9, abs_tol=1e-9,
                    ))

                increased = copy.deepcopy(state)
                increased["tipos_terreno"]["pasto"]["costo"] += 10
                increased_result = ucs(increased, "A1", goal)
                self.assertEqual(increased_result["found"], optimal["found"])
                if optimal["found"]:
                    self.assertGreaterEqual(increased_result["cost"] + 1e-9, optimal["cost"])

                transposed, transposed_goal = transpose_scenario(state, goal)
                transposed_result = ucs(transposed, "A1", transposed_goal)
                self.assertEqual(transposed_result["found"], optimal["found"])
                if optimal["found"]:
                    self.assertTrue(math.isclose(
                        transposed_result["cost"], optimal["cost"],
                        rel_tol=1e-9, abs_tol=1e-9,
                    ))

                self.assertTrue(math.isclose(
                    evaluate(state, "A"), -evaluate(state, "B"),
                    rel_tol=1e-9, abs_tol=1e-9,
                ))
                beam = beam_search(state, "A1", goal, (seed % 4) + 1)
                self.assertGreaterEqual(beam["candidates_discarded"], 0)
                self.assertLessEqual(beam["max_frontier"], (seed % 4) + 1)

    def test_generated_successors_are_legal_valid_and_pure(self) -> None:
        for seed in range(20):
            with self.subTest(seed=seed):
                state, _ = generated_case(seed)
                original = copy.deepcopy(state)
                pairs = action_successors(state)
                self.assertTrue(pairs)
                for action, successor in pairs:
                    self.assertEqual(successor, transition(state, action))
                    validate_state(successor)
                    if successor["juego"]["estado"] != "finalizado":
                        self.assertNotEqual(successor["turno"], state["turno"])
                    active_positions = [
                        (unit["fila"], unit["columna"])
                        for unit in successor["unidades"]
                        if unit.get("activo", True)
                    ]
                    self.assertEqual(len(active_positions), len(set(active_positions)))
                self.assertEqual(state, original)

    def test_state_key_tracks_turn_carrier_activity_and_side(self) -> None:
        state, _ = generated_case(0)
        baseline = state_key(state)

        other_turn = copy.deepcopy(state)
        other_turn["turno"] = "B"
        self.assertNotEqual(baseline, state_key(other_turn))

        carrier = copy.deepcopy(state)
        carrier["juego"]["portador_recurso"] = "A1"
        carrier["recurso"] = None
        self.assertNotEqual(baseline, state_key(carrier))

        inactive = copy.deepcopy(state)
        inactive["unidades"][1]["activo"] = False
        inactive["unidades"][1]["fila"] = -1
        inactive["unidades"][1]["columna"] = -1
        self.assertNotEqual(baseline, state_key(inactive))

        other_side = copy.deepcopy(state)
        other_side["unidades"][0]["bando"] = "B"
        self.assertNotEqual(baseline, state_key(other_side))

        reordered = copy.deepcopy(state)
        reordered["unidades"].reverse()
        self.assertEqual(baseline, state_key(reordered))


if __name__ == "__main__":
    unittest.main()
