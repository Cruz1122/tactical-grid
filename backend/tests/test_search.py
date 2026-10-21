import copy
import json
import unittest
from typing import Any
from unittest.mock import patch

from starlette.types import Message

from backend import main
from backend.algorithms.astar import astar, manhattan, second_heuristic
from backend.algorithms.beam import beam_search
from backend.algorithms.bfs import bfs
from backend.algorithms.dfs import dfs
from backend.algorithms.ucs import ucs
from backend.game import engine as game_engine
from backend.game.engine import (
    hypothetical_move,
    state_key,
    static_state_key,
    transition,
)
from backend.game.movement import legal_moves, move_cost
from backend.game.validation import validate_state
from backend.scenarios import prepare_scenario


def make_state(
    unit_type: str = "estandar",
    start: tuple[int, int] = (3, 3),
    *,
    rows: int = 7,
    columns: int = 7,
    walls: set[tuple[int, int]] | None = None,
    enemies: list[dict[str, Any]] | None = None,
    special_terrain: dict[tuple[int, int], str] | None = None,
    carrier: str | None = None,
    queen_spawn: tuple[int, int] | None = None,
    bases: dict[str, tuple[int, int]] | None = None,
) -> dict[str, Any]:
    walls = walls or set()
    queen_spawn = queen_spawn or (rows - 1, 0)
    bases = bases or {"A": (0, 0), "B": (rows - 1, columns - 1)}
    special_terrain = special_terrain or {}
    terrain = [["camino" for _ in range(columns)] for _ in range(rows)]
    for row, column in walls:
        terrain[row][column] = "muro"
    for (row, column), terrain_id in special_terrain.items():
        terrain[row][column] = terrain_id

    units = [
        {
            "id": "A1",
            "bando": "A",
            "tipo": unit_type,
            "fila": start[0],
            "columna": start[1],
        },
        *(copy.deepcopy(enemies) if enemies else []),
    ]
    scenario: dict[str, Any] = {
        "version": "1.0",
        "mapa": {"filas": rows, "columnas": columns},
        "tipos_terreno": {
            "camino": {"costo": 1, "transitable": True},
            "bosque": {"costo": 3, "transitable": True},
            "pantano": {"costo": 2, "transitable": True},
            "muro": {"transitable": False},
        },
        "terreno": terrain,
        "bases": {
            side: {"fila": position[0], "columna": position[1]}
            for side, position in bases.items()
        },
        "recurso": None if carrier is not None else {"fila": queen_spawn[0], "columna": queen_spawn[1]},
        "unidades": units,
        "turno": "A",
        "juego": {"portador_recurso": carrier},
    }
    if carrier is not None:
        scenario["recurso_spawn"] = {"fila": queen_spawn[0], "columna": queen_spawn[1]}
    return prepare_scenario(scenario)


def replay_path(
    state: dict[str, Any], unit_id: str, path: list[dict[str, int]]
) -> tuple[dict[str, Any], float]:
    current = copy.deepcopy(state)
    total_cost = 0.0
    for step in path[1:]:
        destination = {"fila": step["fila"], "columna": step["columna"]}
        if destination not in legal_moves(current, unit_id):
            raise AssertionError(f"El paso reconstruido no es legal: {destination}")
        total_cost += move_cost(current, unit_id, destination)
        current = hypothetical_move(current, unit_id, destination)
    return current, total_cost


async def post_json(path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    messages: list[Message] = []
    encoded = json.dumps(body).encode("utf-8")
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": encoded, "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "root_path": "",
    }
    await main.app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return status, json.loads(response_body)


class SearchTests(unittest.TestCase):
    def test_both_algorithms_find_reachable_goals(self) -> None:
        state = make_state()
        for algorithm in (bfs, dfs):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(state, "A1", {"fila": 3, "columna": 5})
                self.assertTrue(result["found"])
                self.assertEqual(result["path"][0], {"fila": 3, "columna": 3})
                self.assertEqual(result["path"][-1], {"fila": 3, "columna": 5})
                replayed, cost = replay_path(state, "A1", result["path"])
                self.assertEqual(replayed["unidades"][0]["fila"], 3)
                self.assertEqual(replayed["unidades"][0]["columna"], 5)
                self.assertEqual(cost, result["cost"])

    def test_bfs_finds_the_minimum_number_of_moves(self) -> None:
        state = make_state()
        result = bfs(state, "A1", {"fila": 3, "columna": 5})
        self.assertEqual(result["moves"], 2)

    def test_dfs_can_return_a_longer_path_than_bfs(self) -> None:
        state = make_state()
        target = {"fila": 3, "columna": 5}
        breadth_result = bfs(state, "A1", target)
        depth_result = dfs(state, "A1", target)
        self.assertGreater(depth_result["moves"], breadth_result["moves"])

    def test_origin_equal_to_goal_has_zero_moves_and_cost(self) -> None:
        state = make_state(start=(2, 2))
        for algorithm in (bfs, dfs):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(state, "A1", {"fila": 2, "columna": 2})
                self.assertTrue(result["found"])
                self.assertTrue(result["input_valid"])
                self.assertEqual(result["path"], [{"fila": 2, "columna": 2}])
                self.assertEqual(result["moves"], 0)
                self.assertEqual(result["cost"], 0.0)
                self.assertEqual(result["states_generated"], 1)
                self.assertEqual(result["states_expanded"], 0)

    def test_unreachable_goal_returns_an_explicit_failure(self) -> None:
        walls = {(row, 3) for row in range(7)}
        state = make_state(
            start=(3, 1), walls=walls, bases={"A": (0, 0), "B": (6, 0)}, queen_spawn=(0, 4)
        )
        for algorithm in (bfs, dfs):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(state, "A1", {"fila": 3, "columna": 5})
                self.assertTrue(result["input_valid"])
                self.assertIsNone(result["error"])
                self.assertFalse(result["found"])
                self.assertEqual(result["path"], [])
                self.assertIsNone(result["moves"])
                self.assertIsNone(result["cost"])
                self.assertGreater(result["states_generated"], 0)

    def test_invalid_input_is_distinct_from_valid_but_unreachable_goal(self) -> None:
        state = make_state()
        invalid = bfs(state, "missing", {"fila": 3, "columna": 5})

        self.assertFalse(invalid["input_valid"])
        self.assertIsNotNone(invalid["error"])
        self.assertFalse(invalid["found"])

    def test_ally_occupied_goal_is_valid_but_unreachable(self) -> None:
        state = make_state(
            "rook",
            (2, 0),
            enemies=[{"id": "A2", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 3}],
        )
        for algorithm in (bfs, dfs):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(state, "A1", {"fila": 2, "columna": 3})
                self.assertTrue(result["input_valid"])
                self.assertFalse(result["found"])
                self.assertGreater(result["states_generated"], 0)

    def test_obstacles_and_board_edges_are_respected(self) -> None:
        state = make_state(start=(0, 1), rows=5, columns=5, walls={(0, 2)})
        result = bfs(state, "A1", {"fila": 0, "columna": 3})
        self.assertTrue(result["found"])
        self.assertGreater(result["moves"], 2)
        for point in result["path"]:
            self.assertGreaterEqual(point["fila"], 0)
            self.assertGreaterEqual(point["columna"], 0)
            self.assertNotIn((point["fila"], point["columna"]), {(0, 2)})

    def test_knight_rook_bishop_and_standard_movements(self) -> None:
        cases = (
            ("knight", (2, 2), (4, 3)),
            ("rook", (2, 1), (2, 5)),
            ("bishop", (1, 1), (5, 5)),
            ("estandar", (3, 3), (3, 4)),
        )
        for unit_type, start, goal in cases:
            with self.subTest(unit_type=unit_type):
                state = make_state(unit_type, start)
                result = bfs(state, "A1", {"fila": goal[0], "columna": goal[1]})
                self.assertTrue(result["found"])
                self.assertEqual(result["moves"], 1)

    def test_rook_and_bishop_full_slides_each_count_as_one_move(self) -> None:
        cases = (
            ("rook", (2, 1), (2, 5)),
            ("bishop", (1, 1), (5, 5)),
        )
        for unit_type, start, goal in cases:
            with self.subTest(unit_type=unit_type):
                state = make_state(unit_type, start)
                result = bfs(state, "A1", {"fila": goal[0], "columna": goal[1]})
                self.assertEqual(result["moves"], 1)

    def test_enemy_occupied_goal_is_captured_with_engine_effects(self) -> None:
        state = make_state(
            "rook",
            (2, 0),
            enemies=[{"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 3}],
        )
        state["unidades"][1]["spawn"] = {"fila": 4, "columna": 3}
        original = copy.deepcopy(state)
        result = bfs(state, "A1", {"fila": 2, "columna": 3})
        next_state = hypothetical_move(state, "A1", {"fila": 2, "columna": 3})
        victim = next(unit for unit in next_state["unidades"] if unit["id"] == "B1")

        self.assertTrue(result["found"])
        self.assertEqual(result["path"][-1], {"fila": 2, "columna": 3})
        self.assertTrue(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (4, 3))
        replayed, _ = replay_path(state, "A1", result["path"])
        replayed_victim = next(unit for unit in replayed["unidades"] if unit["id"] == "B1")
        self.assertEqual((replayed_victim["fila"], replayed_victim["columna"]), (4, 3))
        self.assertEqual(state, original)

    def test_capturing_carrier_matches_transition_without_turn_effects(self) -> None:
        state = make_state(
            "rook",
            (2, 0),
            enemies=[{"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 3}],
            carrier="B1",
            queen_spawn=(0, 6),
        )
        state["unidades"][1]["spawn"] = {"fila": 4, "columna": 3}
        original = copy.deepcopy(state)
        destination = {"fila": 2, "columna": 3}
        with patch.object(
            game_engine,
            "_respawn_in_place",
            wraps=game_engine._respawn_in_place,
        ) as hypothetical_respawn:
            next_state = hypothetical_move(state, "A1", destination)
        with patch.object(
            game_engine,
            "_respawn_in_place",
            wraps=game_engine._respawn_in_place,
        ) as transition_respawn:
            actual_state = transition(
                state, {"type": "move", "unit_id": "A1", "destination": destination}
            )

        self.assertEqual(hypothetical_respawn.call_count, 1)
        self.assertEqual(transition_respawn.call_count, 1)
        self.assertEqual(next_state["turno"], state["turno"])
        self.assertEqual(next_state["juego"]["portador_recurso"], None)
        self.assertEqual(next_state["recurso"], {"fila": 0, "columna": 6})
        self.assertEqual(next_state["recurso_spawn"], state["recurso_spawn"])
        victim = next(unit for unit in next_state["unidades"] if unit["id"] == "B1")
        self.assertTrue(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (4, 3))
        self.assertEqual(next_state["recurso"], actual_state["recurso"])
        self.assertEqual(next_state["recurso_spawn"], actual_state["recurso_spawn"])
        self.assertEqual(next_state["juego"]["portador_recurso"], actual_state["juego"]["portador_recurso"])
        self.assertEqual(next_state["unidades"], actual_state["unidades"])
        self.assertNotEqual(state_key(state), state_key(next_state))
        self.assertEqual(state, original)

    def test_carrier_capture_can_leave_queen_under_attacker_without_auto_pickup(self) -> None:
        state = make_state(
            "rook",
            (2, 2),
            enemies=[{"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 3}],
            carrier="B1",
            queen_spawn=(2, 3),
        )
        original = copy.deepcopy(state)
        result = hypothetical_move(state, "A1", {"fila": 2, "columna": 3})

        self.assertEqual(result["juego"]["portador_recurso"], None)
        self.assertEqual(result["recurso"], {"fila": 2, "columna": 3})
        self.assertEqual(result["recurso_spawn"], {"fila": 2, "columna": 3})
        self.assertEqual((result["unidades"][0]["fila"], result["unidades"][0]["columna"]), (2, 3))
        validate_state(result)
        self.assertFalse(result["unidades"][1]["activo"])
        self.assertEqual(state, original)

    def test_search_can_pick_up_and_transport_queen_without_moving_spawn(self) -> None:
        state = make_state("estandar", (2, 1), queen_spawn=(2, 3))
        original = copy.deepcopy(state)
        spawn = copy.deepcopy(state["recurso_spawn"])
        result = bfs(state, "A1", {"fila": 2, "columna": 4})
        final_state, replayed_cost = replay_path(state, "A1", result["path"])

        self.assertTrue(result["found"])
        self.assertEqual(result["moves"], 3)
        self.assertEqual(replayed_cost, result["cost"])
        self.assertEqual(final_state["juego"]["portador_recurso"], "A1")
        self.assertIsNone(final_state["recurso"])
        self.assertEqual(final_state["recurso_spawn"], spawn)
        self.assertEqual(state, original)

    def test_state_key_cache_matches_full_key_and_keeps_dynamic_changes(self) -> None:
        state = make_state("estandar", (2, 1), queen_spawn=(2, 2))
        static_key = static_state_key(state)
        collected = hypothetical_move(state, "A1", {"fila": 2, "columna": 2})
        self.assertEqual(state_key(state), state_key(state, static_key=static_key))
        self.assertEqual(state_key(collected), state_key(collected, static_key=static_key))
        returned = hypothetical_move(collected, "A1", {"fila": 2, "columna": 1})
        self.assertEqual((state["unidades"][0]["fila"], state["unidades"][0]["columna"]), (2, 1))
        self.assertEqual((returned["unidades"][0]["fila"], returned["unidades"][0]["columna"]), (2, 1))
        self.assertNotEqual(state_key(state), state_key(returned))

    def test_route_cost_uses_real_terrain_costs(self) -> None:
        state = make_state(
            "rook",
            (3, 1),
            special_terrain={(3, 2): "bosque", (3, 4): "pantano"},
        )
        result = bfs(state, "A1", {"fila": 3, "columna": 4})
        self.assertEqual(result["moves"], 1)
        self.assertEqual(result["cost"], 6.0)

    def test_metrics_are_consistent_and_results_are_deterministic(self) -> None:
        state = make_state()
        for algorithm in (bfs, dfs):
            with self.subTest(algorithm=algorithm.__name__):
                first = algorithm(state, "A1", {"fila": 3, "columna": 5})
                second = algorithm(state, "A1", {"fila": 3, "columna": 5})

                for field in (
                    "found",
                    "path",
                    "moves",
                    "cost",
                    "states_generated",
                    "states_expanded",
                    "max_frontier",
                ):
                    self.assertEqual(first[field], second[field])
                self.assertGreaterEqual(first["states_generated"], first["states_expanded"] + 1)
                self.assertGreaterEqual(first["max_frontier"], 1)
                self.assertGreaterEqual(first["elapsed_seconds"], 0)
                self.assertGreaterEqual(second["elapsed_seconds"], 0)

    def test_search_does_not_mutate_input_or_require_its_turn(self) -> None:
        state = make_state()
        state["turno"] = "B"
        original = copy.deepcopy(state)
        self.assertTrue(bfs(state, "A1", {"fila": 3, "columna": 5})["found"])
        self.assertTrue(dfs(state, "A1", {"fila": 3, "columna": 5})["found"])
        self.assertEqual(state, original)
        self.assertEqual(state["turno"], "B")


class UniformCostSearchTests(unittest.TestCase):
    def test_origin_goal_unreachable_and_invalid_unit(self) -> None:
        state = make_state(start=(2, 2))
        result = ucs(state, "A1", {"fila": 2, "columna": 2})

        self.assertTrue(result["found"])
        self.assertEqual(result["path"], [{"fila": 2, "columna": 2}])
        self.assertEqual(result["moves"], 0)
        self.assertEqual(result["cost"], 0.0)
        self.assertEqual(result["states_generated"], 1)
        self.assertEqual(result["states_expanded"], 0)

        barrier = {(row, 3) for row in range(7)}
        blocked = make_state(
            start=(3, 1), walls=barrier,
            bases={"A": (0, 0), "B": (6, 0)}, queen_spawn=(0, 4),
        )
        unreachable = ucs(blocked, "A1", {"fila": 3, "columna": 5})
        self.assertTrue(unreachable["input_valid"])
        self.assertIsNone(unreachable["error"])
        self.assertFalse(unreachable["found"])
        self.assertEqual(unreachable["path"], [])
        self.assertIsNone(unreachable["moves"])
        self.assertIsNone(unreachable["cost"])

        invalid = ucs(state, "missing", {"fila": 2, "columna": 3})
        self.assertFalse(invalid["input_valid"])
        self.assertFalse(invalid["found"])
        self.assertIsNotNone(invalid["error"])

    def test_bfs_prefers_fewer_moves_while_ucs_prefers_lower_terrain_cost(self) -> None:
        state = make_state(
            "estandar", (3, 0),
            special_terrain={(3, 1): "bosque", (3, 2): "bosque", (3, 3): "bosque"},
        )
        goal = {"fila": 3, "columna": 4}
        breadth = bfs(state, "A1", goal)
        uniform = ucs(state, "A1", goal)
        informed = astar(state, "A1", goal, "second")
        replayed, replay_cost = replay_path(state, "A1", uniform["path"])

        self.assertEqual(breadth["moves"], 4)
        self.assertEqual(breadth["cost"], 10.0)
        self.assertEqual(uniform["moves"], 6)
        self.assertEqual(uniform["cost"], 6.0)
        self.assertEqual(informed["cost"], uniform["cost"])
        self.assertEqual(replay_cost, uniform["cost"])
        self.assertEqual(uniform["path"][0], {"fila": 3, "columna": 0})
        self.assertEqual(uniform["path"][-1], goal)
        self.assertEqual((replayed["unidades"][0]["fila"], replayed["unidades"][0]["columna"]), (3, 4))

    def test_all_unit_types_and_long_slides_use_real_terrain_costs(self) -> None:
        cases = (
            ("knight", (2, 2), (4, 3), {}, set(), 1.0),
            ("estandar", (3, 3), (3, 4), {}, set(), 1.0),
            (
                "rook", (3, 1), (3, 5),
                {(3, 2): "bosque", (3, 3): "pantano"},
                {(row, column) for row in (2, 4) for column in range(1, 6)}, 7.0,
            ),
        )
        for unit_type, start, destination, terrain, walls, expected_cost in cases:
            with self.subTest(unit_type=unit_type):
                state = make_state(
                    unit_type, start, special_terrain=terrain, walls=walls
                )
                result = ucs(
                    state, "A1",
                    {"fila": destination[0], "columna": destination[1]},
                )
                replayed, replay_cost = replay_path(state, "A1", result["path"])

                self.assertTrue(result["found"])
                self.assertEqual(result["moves"], 1)
                self.assertEqual(result["cost"], expected_cost)
                self.assertEqual(replay_cost, expected_cost)
                self.assertEqual(replayed["unidades"][0]["fila"], destination[0])

        bishop_open = {(index, index) for index in range(7)}
        bishop_open.update((0, column) for column in range(7))
        bishop_open.update((row, 6) for row in range(7))
        bishop_open.add((6, 0))
        bishop_walls = {
            (row, column)
            for row in range(7)
            for column in range(7)
            if (row, column) not in bishop_open
        }
        bishop_state = make_state(
            "bishop", (1, 1), walls=bishop_walls,
            special_terrain={(2, 2): "bosque", (3, 3): "pantano", (4, 4): "bosque"},
            queen_spawn=(6, 0), bases={"A": (0, 0), "B": (6, 6)},
        )
        bishop = ucs(bishop_state, "A1", {"fila": 5, "columna": 5})
        bishop_replayed, bishop_cost = replay_path(bishop_state, "A1", bishop["path"])
        self.assertTrue(bishop["found"])
        self.assertEqual(bishop["moves"], 1)
        self.assertEqual(bishop["cost"], 9.0)
        self.assertEqual(bishop_cost, 9.0)
        self.assertEqual(bishop_replayed["unidades"][0]["columna"], 5)

    def test_positive_decimal_transition_cost_is_preserved(self) -> None:
        state = make_state("knight", (1, 1))
        state["tipos_terreno"]["barato"] = {"costo": 0.25, "transitable": True}
        state["terreno"][3][2] = "barato"

        result = ucs(state, "A1", {"fila": 3, "columna": 2})

        self.assertTrue(result["found"])
        self.assertEqual(result["moves"], 1)
        self.assertEqual(result["cost"], 0.25)

    def test_cost_improvements_discard_stale_heap_entries_and_cycles(self) -> None:
        state = make_state(start=(2, 2))
        graph = {
            (2, 2): [((2, 3), 5.0), ((3, 2), 1.0)],
            (3, 2): [((2, 3), 1.0), ((2, 2), 0.5)],
            (2, 3): [((2, 4), 10.0)],
        }

        def move_to(current: dict[str, Any], position: tuple[int, int]) -> dict[str, Any]:
            next_state = copy.deepcopy(current)
            unit = next(item for item in next_state["unidades"] if item["id"] == "A1")
            unit["fila"], unit["columna"] = position
            return next_state

        def graph_successors(current: dict[str, Any], _unit_id: str):
            position = (current["unidades"][0]["fila"], current["unidades"][0]["columna"])
            return [
                (move_to(current, destination), cost)
                for destination, cost in graph.get(position, [])
            ]

        with patch("backend.algorithms.ucs.unit_successors", side_effect=graph_successors) as successors:
            result = ucs(state, "A1", {"fila": 2, "columna": 4})

        self.assertTrue(result["found"])
        self.assertEqual(result["cost"], 12.0)
        self.assertEqual(
            result["path"],
            [
                {"fila": 2, "columna": 2}, {"fila": 3, "columna": 2},
                {"fila": 2, "columna": 3}, {"fila": 2, "columna": 4},
            ],
        )
        self.assertEqual(result["states_generated"], 4)
        self.assertEqual(result["states_expanded"], 3)
        self.assertEqual(successors.call_count, 3)

    def test_capture_respawn_and_queen_spawn_are_hypothetical(self) -> None:
        state = make_state(
            "rook", (2, 0),
            enemies=[{"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 3}],
            carrier="B1", queen_spawn=(0, 6),
        )
        state["unidades"][1]["spawn"] = {"fila": 4, "columna": 3}
        state["turno"] = "B"
        original = copy.deepcopy(state)
        result = ucs(state, "A1", {"fila": 2, "columna": 3})
        captured_state, replay_cost = replay_path(state, "A1", result["path"])
        victim = next(unit for unit in captured_state["unidades"] if unit["id"] == "B1")

        self.assertTrue(result["found"])
        self.assertEqual(replay_cost, result["cost"])
        self.assertEqual(captured_state["juego"]["portador_recurso"], None)
        self.assertEqual(captured_state["recurso"], {"fila": 0, "columna": 6})
        self.assertEqual(captured_state["recurso_spawn"], {"fila": 0, "columna": 6})
        self.assertTrue(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (4, 3))
        self.assertEqual(state, original)

    def test_deterministic_metrics_and_official_state_isolation(self) -> None:
        state = make_state(start=(3, 3), walls={(2, 3), (4, 3)})
        state["turno"] = "B"
        original = copy.deepcopy(state)
        goal = {"fila": 3, "columna": 5}
        first = ucs(state, "A1", goal)
        second = ucs(state, "A1", goal)

        for field in (
            "found", "path", "moves", "cost", "states_generated",
            "states_expanded", "max_frontier",
        ):
            self.assertEqual(first[field], second[field])
        self.assertGreaterEqual(first["states_generated"], first["states_expanded"] + 1)
        self.assertGreaterEqual(first["max_frontier"], 1)
        self.assertGreaterEqual(first["elapsed_seconds"], 0)
        self.assertGreaterEqual(second["elapsed_seconds"], 0)
        self.assertEqual(state, original)


class BeamSearchTests(unittest.TestCase):
    def test_origin_goal_and_invalid_widths(self) -> None:
        state = make_state(start=(2, 2))
        original = copy.deepcopy(state)
        result = beam_search(state, "A1", {"fila": 2, "columna": 2}, 1)

        self.assertTrue(result["found"])
        self.assertEqual(result["path"], [{"fila": 2, "columna": 2}])
        self.assertEqual(result["moves"], 0)
        self.assertEqual(result["cost"], 0.0)
        self.assertEqual(result["max_frontier"], 1)
        self.assertEqual(result["candidates_discarded"], 0)
        self.assertEqual(state, original)
        for invalid_width in (0, -1, -4):
            with self.subTest(k=invalid_width):
                invalid_result = beam_search(
                    state, "A1", {"fila": 2, "columna": 3}, invalid_width
                )
                self.assertFalse(invalid_result["input_valid"])
                self.assertFalse(invalid_result["found"])
                self.assertTrue(invalid_result["error"])
                self.assertEqual(invalid_result["path"], [])
                self.assertEqual(invalid_result["candidates_discarded"], 0)
        self.assertEqual(state, original)

    def test_widths_find_routes_and_frontier_never_exceeds_k(self) -> None:
        state = make_state(start=(3, 3))
        target = {"fila": 3, "columna": 5}
        for width in (1, 2, 4, 8):
            with self.subTest(k=width):
                result = beam_search(state, "A1", target, width)
                self.assertTrue(result["found"])
                self.assertEqual(result["path"][-1], target)
                self.assertLessEqual(result["max_frontier"], width)
                replayed, cost = replay_path(state, "A1", result["path"])
                self.assertEqual(cost, result["cost"])
                self.assertEqual((replayed["unidades"][0]["fila"], replayed["unidades"][0]["columna"]), (3, 5))

    def test_unreachable_goal_returns_explicit_failure(self) -> None:
        barrier = {(row, 3) for row in range(7)}
        state = make_state(
            start=(3, 1), walls=barrier,
            bases={"A": (0, 0), "B": (6, 0)}, queen_spawn=(0, 4),
        )
        result = beam_search(state, "A1", {"fila": 3, "columna": 5}, 8)

        self.assertTrue(result["input_valid"])
        self.assertFalse(result["found"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["path"], [])
        self.assertIsNone(result["moves"])
        self.assertIsNone(result["cost"])
        self.assertGreater(result["states_generated"], 0)
        self.assertGreaterEqual(result["candidates_discarded"], 0)

    def test_larger_width_than_candidate_count_discards_nothing(self) -> None:
        state = make_state(start=(3, 3))
        result = beam_search(state, "A1", {"fila": 2, "columna": 3}, 8)

        self.assertTrue(result["found"])
        self.assertEqual(result["candidates_discarded"], 0)
        self.assertLessEqual(result["max_frontier"], 4)

    def test_ties_are_deterministic_and_follow_real_successor_order(self) -> None:
        state = make_state(start=(3, 3))
        goal = {"fila": 1, "columna": 2}
        first = beam_search(state, "A1", goal, 1)
        second = beam_search(state, "A1", goal, 1)

        self.assertEqual(first["path"], second["path"])
        self.assertEqual(first["path"][1], {"fila": 2, "columna": 3})

    def test_cycles_and_duplicate_states_are_not_reexpanded(self) -> None:
        state = make_state(
            start=(2, 2), rows=5, columns=5,
            enemies=[{"id": "A2", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 3}],
        )
        result = beam_search(state, "A1", {"fila": 2, "columna": 3}, 100)

        self.assertFalse(result["found"])
        self.assertGreater(result["states_generated"], 1)
        self.assertLessEqual(result["states_generated"], 2 * 5 * 5)
        self.assertEqual(result["states_expanded"], result["states_generated"])
        self.assertLessEqual(result["max_frontier"], 100)

    def test_weighted_route_cost_and_input_state_are_preserved(self) -> None:
        state = make_state(
            "rook", (3, 1),
            special_terrain={(3, 2): "bosque", (3, 4): "pantano"},
        )
        original = copy.deepcopy(state)
        result = beam_search(state, "A1", {"fila": 3, "columna": 4}, 8)
        replayed, cost = replay_path(state, "A1", result["path"])

        self.assertTrue(result["found"])
        self.assertEqual(result["moves"], 1)
        self.assertEqual(cost, 6.0)
        self.assertEqual(result["cost"], cost)
        self.assertEqual(replayed["unidades"][0]["columna"], 4)
        self.assertEqual(state, original)

    def test_hypothetical_capture_resets_queen_to_original_spawn(self) -> None:
        state = make_state(
            "rook", (2, 0),
            enemies=[{"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 3}],
            carrier="B1", queen_spawn=(0, 6),
        )
        state["unidades"][1]["spawn"] = {"fila": 4, "columna": 3}
        original = copy.deepcopy(state)
        result = beam_search(state, "A1", {"fila": 2, "columna": 3}, 4)
        captured_state, cost = replay_path(state, "A1", result["path"])
        victim = next(unit for unit in captured_state["unidades"] if unit["id"] == "B1")

        self.assertTrue(result["found"])
        self.assertEqual(cost, result["cost"])
        self.assertEqual(captured_state["recurso"], {"fila": 0, "columna": 6})
        self.assertEqual(captured_state["recurso_spawn"], {"fila": 0, "columna": 6})
        self.assertTrue(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (4, 3))
        self.assertEqual(state, original)

    def test_queen_pickup_uses_hypothetical_state_without_moving_spawn(self) -> None:
        state = make_state("estandar", (2, 1), queen_spawn=(2, 3))
        original = copy.deepcopy(state)
        spawn = copy.deepcopy(state["recurso_spawn"])
        result = beam_search(state, "A1", {"fila": 2, "columna": 4}, 100)
        final_state, cost = replay_path(state, "A1", result["path"])

        self.assertTrue(result["found"])
        self.assertEqual(result["cost"], cost)
        self.assertEqual(final_state["juego"]["portador_recurso"], "A1")
        self.assertIsNone(final_state["recurso"])
        self.assertEqual(final_state["recurso_spawn"], spawn)
        self.assertEqual(state, original)

    def test_narrow_beam_can_discard_a_solution_that_bfs_finds(self) -> None:
        walls = {
            (1, 0), (1, 2), (2, 1), (3, 0), (3, 3),
            (4, 1), (4, 2), (4, 3),
        }
        state = make_state(
            start=(2, 2), rows=5, columns=5, walls=walls,
            queen_spawn=(4, 0), bases={"A": (0, 0), "B": (4, 4)},
        )
        goal = {"fila": 4, "columna": 4}
        breadth_result = bfs(state, "A1", goal)
        results = {width: beam_search(state, "A1", goal, width) for width in (1, 2, 4, 8)}

        self.assertTrue(breadth_result["found"])
        self.assertFalse(results[1]["found"])
        self.assertGreater(results[1]["candidates_discarded"], 0)
        for width in (2, 4, 8):
            with self.subTest(k=width):
                self.assertTrue(results[width]["found"])
                self.assertLessEqual(results[width]["max_frontier"], width)
                replayed, cost = replay_path(state, "A1", results[width]["path"])
                self.assertEqual(results[width]["cost"], cost)
                self.assertEqual((replayed["unidades"][0]["fila"], replayed["unidades"][0]["columna"]), (4, 4))


class AStarTests(unittest.TestCase):
    def test_start_equal_to_goal_and_unreachable_goal(self) -> None:
        state = make_state(start=(2, 2))
        for heuristic in ("manhattan", "second"):
            result = astar(state, "A1", {"fila": 2, "columna": 2}, heuristic)
            self.assertTrue(result["found"])
            self.assertEqual(result["path"], [{"fila": 2, "columna": 2}])
            self.assertEqual(result["moves"], 0)
            self.assertEqual(result["cost"], 0.0)
            self.assertEqual(result["states_generated"], 1)
            self.assertEqual(result["states_expanded"], 0)

        barrier = {(row, 3) for row in range(7)}
        state = make_state(
            start=(3, 1),
            walls=barrier,
            bases={"A": (0, 0), "B": (6, 0)},
            queen_spawn=(0, 4),
        )
        result = astar(state, "A1", {"fila": 3, "columna": 5}, "second")
        self.assertTrue(result["input_valid"])
        self.assertFalse(result["found"])
        self.assertEqual(result["path"], [])
        self.assertIsNone(result["cost"])

    def test_obstacles_and_different_terrain_costs_produce_legal_paths(self) -> None:
        state = make_state(
            start=(0, 1), rows=5, columns=5, walls={(0, 2)},
            special_terrain={(1, 1): "pantano", (1, 2): "bosque"},
        )
        original = copy.deepcopy(state)
        result = astar(state, "A1", {"fila": 0, "columna": 3}, "second")
        replayed, cost = replay_path(state, "A1", result["path"])

        self.assertTrue(result["found"])
        self.assertGreater(result["moves"], 2)
        self.assertEqual(cost, result["cost"])
        self.assertEqual(replayed["unidades"][0]["columna"], 3)
        self.assertEqual(state, original)

        rook_state = make_state(
            "rook", (3, 1), special_terrain={(3, 2): "bosque", (3, 3): "pantano"}
        )
        weighted = astar(rook_state, "A1", {"fila": 3, "columna": 4}, "second")
        self.assertEqual(weighted["cost"], 5.0)
        self.assertEqual(weighted["moves"], 3)

    def test_positive_terrain_cost_below_one_is_respected(self) -> None:
        state = make_state("rook", (0, 0), rows=3, columns=3)
        state["tipos_terreno"]["barato"] = {"costo": 0.25, "transitable": True}
        state["terreno"][0][2] = "barato"

        estimate = second_heuristic(state, (0, 0), (0, 2), "rook")
        result = astar(state, "A1", {"fila": 0, "columna": 2}, "second")

        self.assertEqual(estimate, 0.5)
        self.assertTrue(result["found"])
        self.assertEqual(result["cost"], 1.25)

    def test_empty_rows_and_columns_use_conservative_zero_minima(self) -> None:
        state = make_state("estandar", (0, 0), rows=3, columns=3)
        state["terreno"][1] = ["muro"] * 3
        self.assertEqual(second_heuristic(state, (0, 0), (2, 2), "estandar"), 3.0)

        state = make_state("estandar", (0, 0), rows=3, columns=3)
        for row in state["terreno"]:
            row[1] = "muro"
        self.assertEqual(second_heuristic(state, (0, 0), (2, 2), "estandar"), 3.0)

    def test_both_heuristics_search_all_four_unit_types(self) -> None:
        cases = (
            ("estandar", (2, 2), (2, 3), 1.0),
            ("rook", (2, 1), (2, 5), 4.0),
            ("bishop", (1, 1), (5, 5), 4.0),
            ("knight", (2, 2), (4, 3), 1.0),
        )
        for unit_type, start, goal, expected_cost in cases:
            state = make_state(unit_type, start)
            for heuristic in ("manhattan", "second"):
                with self.subTest(unit_type=unit_type, heuristic=heuristic):
                    result = astar(
                        state, "A1", {"fila": goal[0], "columna": goal[1]}, heuristic
                    )
                    replayed, cost = replay_path(state, "A1", result["path"])
                    self.assertTrue(result["found"])
                    self.assertEqual(result["path"][-1], {"fila": goal[0], "columna": goal[1]})
                    self.assertEqual(cost, result["cost"])
                    self.assertEqual(result["cost"], expected_cost)
                    self.assertEqual(replayed["unidades"][0]["fila"], goal[0])

    def test_standard_heuristic_matches_the_documented_three_by_three_example(self) -> None:
        state = make_state("estandar", (0, 0), rows=3, columns=3)
        state["tipos_terreno"].update(
            {
                "costo_2": {"costo": 2, "transitable": True},
                "costo_3": {"costo": 3, "transitable": True},
                "costo_4": {"costo": 4, "transitable": True},
            }
        )
        state["terreno"] = [
            ["camino", "costo_2", "camino"],
            ["costo_3", "costo_4", "costo_3"],
            ["camino", "costo_2", "camino"],
        ]

        self.assertEqual(manhattan((0, 0), (2, 2)), 4)
        self.assertEqual(second_heuristic(state, (0, 0), (2, 2), "estandar"), 7)
        self.assertEqual(second_heuristic(state, (1, 1), (2, 2), "estandar"), 2)

    def test_second_heuristic_is_consistent_on_legal_moves(self) -> None:
        target = (4, 4)
        for unit_type in ("estandar", "rook", "bishop", "knight"):
            state = make_state(
                unit_type,
                (0, 0),
                rows=5,
                columns=5,
                walls={(1, 3)},
                special_terrain={(0, 1): "bosque", (2, 2): "pantano", (4, 3): "bosque"},
            )
            for row in range(5):
                for column in range(5):
                    if (row, column) == (1, 3):
                        continue
                    state["unidades"][0]["fila"] = row
                    state["unidades"][0]["columna"] = column
                    position = (row, column)
                    estimate = second_heuristic(state, position, target, unit_type)
                    for destination in legal_moves(state, "A1"):
                        next_position = (destination["fila"], destination["columna"])
                        step_cost = move_cost(state, "A1", destination)
                        next_estimate = second_heuristic(
                            state, next_position, target, unit_type
                        )
                        self.assertLessEqual(
                            estimate,
                            step_cost + next_estimate + 1e-9,
                            (unit_type, position, next_position),
                        )
            self.assertEqual(second_heuristic(state, target, target, unit_type), 0)

    def test_second_heuristic_is_admissible_against_known_optimal_direct_routes(self) -> None:
        cases = (
            ("estandar", (2, 2), (2, 3), 1.0),
            ("rook", (2, 1), (2, 5), 4.0),
            ("bishop", (1, 1), (5, 5), 4.0),
            ("knight", (2, 2), (4, 3), 1.0),
        )
        for unit_type, start, goal, optimal_cost in cases:
            state = make_state(unit_type, start)
            estimate = second_heuristic(state, start, goal, unit_type)
            result = astar(state, "A1", {"fila": goal[0], "columna": goal[1]}, "second")
            self.assertLessEqual(estimate, optimal_cost)
            self.assertEqual(result["cost"], optimal_cost)

    def test_hypothetical_capture_and_queen_spawn_are_preserved(self) -> None:
        state = make_state(
            "rook",
            (2, 0),
            enemies=[{"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 3}],
            carrier="B1",
            queen_spawn=(0, 6),
        )
        state["unidades"][1]["spawn"] = {"fila": 4, "columna": 3}
        original = copy.deepcopy(state)
        captured = astar(state, "A1", {"fila": 2, "columna": 3}, "second")
        captured_state, _ = replay_path(state, "A1", captured["path"])
        victim = next(unit for unit in captured_state["unidades"] if unit["id"] == "B1")

        self.assertTrue(captured["found"])
        self.assertEqual((victim["fila"], victim["columna"]), (4, 3))
        self.assertEqual(captured_state["recurso"], {"fila": 0, "columna": 6})
        self.assertEqual(captured_state["recurso_spawn"], {"fila": 0, "columna": 6})

        transport = make_state("estandar", (2, 1), queen_spawn=(2, 3))
        transport_original = copy.deepcopy(transport)
        spawn = copy.deepcopy(transport["recurso_spawn"])
        result = astar(transport, "A1", {"fila": 2, "columna": 4}, "second")
        final_state, _ = replay_path(transport, "A1", result["path"])
        self.assertEqual(final_state["juego"]["portador_recurso"], "A1")
        self.assertEqual(final_state["recurso_spawn"], spawn)
        self.assertEqual(transport, transport_original)
        self.assertEqual(state, original)

    def test_search_metrics_and_routes_are_deterministic_without_mutation(self) -> None:
        state = make_state(start=(3, 3), walls={(2, 3), (4, 3)})
        state["turno"] = "B"
        original = copy.deepcopy(state)
        first = astar(state, "A1", {"fila": 3, "columna": 5}, "second")
        second = astar(state, "A1", {"fila": 3, "columna": 5}, "second")

        for field in (
            "found", "path", "moves", "cost", "states_generated", "states_expanded", "max_frontier"
        ):
            self.assertEqual(first[field], second[field])
        self.assertEqual(state, original)
        self.assertGreaterEqual(first["states_generated"], first["states_expanded"] + 1)
        self.assertGreaterEqual(first["max_frontier"], 1)
        self.assertGreaterEqual(first["elapsed_seconds"], 0)


class SearchApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        with main.lock:
            self.current_state = copy.deepcopy(main.current_state)
            self.source_name = main.source_name

    def tearDown(self) -> None:
        with main.lock:
            main.current_state = self.current_state
            main.source_name = self.source_name

    async def test_search_endpoint_supports_bfs_and_dfs_without_mutating_state(self) -> None:
        state = make_state("estandar", (3, 3))
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        for algorithm in ("bfs", "dfs"):
            with self.subTest(algorithm=algorithm):
                status, response = await post_json(
                    "/api/search",
                    {"algorithm": algorithm, "unit_id": "A1", "goal": {"row": 3, "column": 5}},
                )

                self.assertEqual(status, 200)
                self.assertTrue(response["result"]["found"])
                self.assertTrue(response["result"]["input_valid"])
                self.assertEqual(response["result"]["path"][-1], {"fila": 3, "columna": 5})
                self.assertEqual(response["result"]["cost"], float(response["result"]["moves"]))
                self.assertEqual(main.current_state, original)
        self.assertEqual(main.current_state, original)

    async def test_ucs_is_available_on_search_and_search_test_endpoints(self) -> None:
        state = make_state("estandar", (3, 3))
        state["prueba"] = {
            "modo": "busqueda",
            "unidad_inicio": "A1",
            "objetivo": {"fila": 3, "columna": 5},
        }
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        status, response = await post_json(
            "/api/search",
            {"algorithm": "ucs", "unit_id": "A1", "goal": {"row": 3, "column": 5}},
        )
        self.assertEqual(status, 200)
        self.assertTrue(response["result"]["found"])
        self.assertEqual(response["result"]["path"][-1], {"fila": 3, "columna": 5})

        test_status, test_response = await post_json("/api/test", {"algorithm": "ucs"})
        self.assertEqual(test_status, 200)
        self.assertEqual(test_response["mode"], "busqueda")
        self.assertTrue(test_response["result"]["found"])
        self.assertEqual(main.current_state, original)

    async def test_astar_heuristics_are_available_on_search_and_test_endpoints(self) -> None:
        state = make_state("estandar", (0, 0), rows=3, columns=3)
        state["prueba"] = {
            "modo": "busqueda",
            "unidad_inicio": "A1",
            "objetivo": {"fila": 2, "columna": 2},
        }
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        for heuristic in ("manhattan", "second"):
            with self.subTest(endpoint="search", heuristic=heuristic):
                status, response = await post_json(
                    "/api/search",
                    {
                        "algorithm": "astar",
                        "unit_id": "A1",
                        "goal": {"row": 2, "column": 2},
                        "heuristic": heuristic,
                    },
                )
                self.assertEqual(status, 200)
                self.assertTrue(response["result"]["found"])
                self.assertEqual(response["result"]["path"][-1], {"fila": 2, "columna": 2})

            with self.subTest(endpoint="test", heuristic=heuristic):
                status, response = await post_json(
                    "/api/test", {"algorithm": "astar", "heuristic": heuristic}
                )
                self.assertEqual(status, 200)
                self.assertEqual(response["mode"], "busqueda")
                self.assertTrue(response["result"]["found"])

        self.assertEqual(main.current_state, original)

    async def test_search_test_mode_dispatches_to_dfs(self) -> None:
        state = make_state("estandar", (3, 3))
        state["prueba"] = {
            "modo": "busqueda",
            "unidad_inicio": "A1",
            "objetivo": {"fila": 3, "columna": 5},
        }
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        status, response = await post_json("/api/test", {"algorithm": "dfs"})

        self.assertEqual(status, 200)
        self.assertEqual(response["mode"], "busqueda")
        self.assertTrue(response["result"]["found"])
        self.assertEqual(main.current_state, original)

    async def test_beam_search_and_test_endpoints_use_k_without_mutation(self) -> None:
        state = make_state("estandar", (3, 3))
        state["prueba"] = {
            "modo": "busqueda",
            "unidad_inicio": "A1",
            "objetivo": {"fila": 3, "columna": 5},
        }
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        status, response = await post_json(
            "/api/search",
            {
                "algorithm": "beam", "unit_id": "A1",
                "goal": {"row": 3, "column": 5}, "k": 4,
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(response["result"]["found"])
        self.assertLessEqual(response["result"]["max_frontier"], 4)
        self.assertIn("candidates_discarded", response["result"])

        test_status, test_response = await post_json(
            "/api/test", {"algorithm": "beam", "k": 4}
        )
        self.assertEqual(test_status, 200)
        self.assertEqual(test_response["mode"], "busqueda")
        self.assertTrue(test_response["result"]["found"])

        invalid_status, _ = await post_json(
            "/api/search",
            {
                "algorithm": "beam", "unit_id": "A1",
                "goal": {"row": 3, "column": 5}, "k": 0,
            },
        )
        self.assertEqual(invalid_status, 422)
        self.assertEqual(main.current_state, original)
