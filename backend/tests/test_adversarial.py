import copy
import json
import unittest
from typing import Any
from unittest.mock import patch

from starlette.types import Message

from backend import main
from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.evaluation import evaluate
from backend.algorithms.minimax import minimax
from backend.game.engine import action_successors, transition
from backend.game.movement import is_in_check
from backend.scenarios import prepare_scenario


def make_state(
    units: list[dict[str, Any]],
    *,
    rows: int = 6,
    columns: int = 6,
    queen: tuple[int, int] | None = (3, 3),
    turn: str = "A",
    bases: dict[str, tuple[int, int]] | None = None,
    carrier: str | None = None,
    queen_spawn: tuple[int, int] | None = None,
    kings: dict[str, list[dict[str, int]]] | None = None,
) -> dict[str, Any]:
    bases = bases or {"A": (0, 0), "B": (rows - 1, columns - 1)}
    scenario: dict[str, Any] = {
        "version": "1.0",
        "mapa": {"filas": rows, "columnas": columns},
        "tipos_terreno": {
            "camino": {"costo": 1, "transitable": True},
            "muro": {"transitable": False},
        },
        "terreno": [["camino" for _ in range(columns)] for _ in range(rows)],
        "bases": {
            side: {"fila": position[0], "columna": position[1]}
            for side, position in bases.items()
        },
        "recurso": (
            None
            if carrier is not None
            else {"fila": queen[0], "columna": queen[1]} if queen is not None else None
        ),
        "unidades": copy.deepcopy(units),
        "turno": turn,
        "juego": {"portador_recurso": carrier},
    }
    if carrier is not None:
        spawn = queen_spawn or (rows - 1, 0)
        scenario["recurso_spawn"] = {"fila": spawn[0], "columna": spawn[1]}
    if kings is not None:
        scenario["reyes"] = copy.deepcopy(kings)
    return prepare_scenario(scenario)


def tactical_state() -> dict[str, Any]:
    """Estado 6x6 reproducible: capturar a B1 evita que capture al portador."""
    return make_state(
        [
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 3, "columna": 2},
            {"id": "A2", "bando": "A", "tipo": "rook", "fila": 0, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 3, "columna": 1},
            {"id": "B2", "bando": "B", "tipo": "estandar", "fila": 0, "columna": 5},
        ],
        queen=(3, 3),
    )


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


class AdversarialEvaluationTests(unittest.TestCase):
    def test_terminal_win_loss_and_draw_override_positional_scores(self) -> None:
        won = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 4},
            ],
            carrier="A1",
            queen_spawn=(3, 3),
        )
        drawn = make_state(
            [
                {
                    "id": "A1", "bando": "A", "tipo": "estandar",
                    "fila": 1, "columna": 1, "activo": False,
                },
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 4},
            ]
        )

        self.assertEqual(evaluate(won, "A"), 100_000)
        self.assertEqual(evaluate(won, "B"), -100_000)
        self.assertEqual(evaluate(drawn, "A"), 0)
        self.assertEqual(evaluate(drawn, "B"), 0)

    def test_evaluation_is_symmetric_and_uses_normalized_map_distances(self) -> None:
        state = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 5, "columna": 5},
            ],
            queen=(0, 1),
        )

        self.assertEqual(evaluate(state, "A"), -evaluate(state, "B"))
        self.assertAlmostEqual(evaluate(state, "A"), 360.0)

    def test_check_is_valued_only_while_the_queen_is_free(self) -> None:
        checking = make_state(
            [{"id": "A1", "bando": "A", "tipo": "rook", "fila": 2, "columna": 0}],
            queen=(4, 4),
            bases={"A": (5, 0), "B": (5, 5)},
            kings={"A": [], "B": [{"fila": 0, "columna": 0}]},
        )
        not_checking = copy.deepcopy(checking)
        not_checking["reyes"]["B"][0]["columna"] = 1

        self.assertTrue(is_in_check(checking, "B"))
        self.assertFalse(is_in_check(not_checking, "B"))
        self.assertEqual(evaluate(checking, "A") - evaluate(not_checking, "A"), 80)

    def test_possession_and_immediate_carrier_safety_have_distinct_values(self) -> None:
        safe = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            ],
            carrier="A1",
            queen_spawn=(3, 3),
        )
        threatened = copy.deepcopy(safe)
        threatened["unidades"][1]["fila"] = 1
        threatened["unidades"][1]["columna"] = 5

        self.assertEqual(evaluate(safe, "A"), 1_060)
        self.assertEqual(evaluate(safe, "A") - evaluate(threatened, "A"), 325)
        self.assertEqual(evaluate(safe, "A"), -evaluate(safe, "B"))

    def test_active_and_inactive_units_are_counted_and_only_active_units_move(self) -> None:
        active = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
                {"id": "A2", "bando": "A", "tipo": "rook", "fila": 2, "columna": 1},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 4},
            ],
            carrier="A1",
            queen_spawn=(3, 3),
        )
        inactive = copy.deepcopy(active)
        inactive["unidades"][1]["activo"] = False
        inactive["unidades"][1]["fila"] = -1
        inactive["unidades"][1]["columna"] = -1

        self.assertEqual(evaluate(active, "A") - evaluate(inactive, "A"), 60)
        self.assertNotIn("A2", {action["unit_id"] for action, _ in action_successors(inactive)})

    def test_check_prevents_queen_pickup_but_not_transport_or_delivery(self) -> None:
        checked = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 3, "columna": 0},
            ],
            queen=(0, 0),
            kings={"A": [{"fila": 3, "columna": 3}], "B": []},
        )
        delivering = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 0, "columna": 5},
            ],
            carrier="A1",
            queen_spawn=(3, 3),
            kings={"A": [{"fila": 0, "columna": 1}], "B": []},
        )

        self.assertTrue(is_in_check(checked, "A"))
        self.assertFalse(any(action["type"] == "collect" for action, _ in action_successors(checked)))
        self.assertTrue(is_in_check(delivering, "A"))
        won = transition(
            delivering,
            {"type": "move", "unit_id": "A1", "destination": {"fila": 0, "columna": 0}},
        )
        self.assertEqual(won["juego"]["resultado"], "A")

    def test_capture_of_carrier_returns_queen_to_original_spawn_without_pickup(self) -> None:
        state = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
            ],
            carrier="B1",
            queen_spawn=(3, 3),
        )
        capture = next(
            next_state
            for action, next_state in action_successors(state)
            if action["unit_id"] == "A1"
            and action["type"] == "move"
            and action["destination"] == {"fila": 1, "columna": 2}
        )

        self.assertIsNone(capture["juego"]["portador_recurso"])
        self.assertEqual(capture["recurso"], {"fila": 3, "columna": 3})
        self.assertEqual(capture["recurso_spawn"], {"fila": 3, "columna": 3})
        self.assertFalse(next(unit for unit in capture["unidades"] if unit["id"] == "B1")["activo"])

    def test_actions_include_all_three_active_units_and_alternate_real_turns(self) -> None:
        state = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 0},
                {"id": "A2", "bando": "A", "tipo": "knight", "fila": 1, "columna": 2},
                {"id": "A3", "bando": "A", "tipo": "rook", "fila": 2, "columna": 4},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 5},
            ]
        )
        original = copy.deepcopy(state)
        pairs = action_successors(state)
        first = pairs[0][1]
        enemy_pairs = action_successors(first)

        self.assertEqual({action["unit_id"] for action, _ in pairs}, {"A1", "A2", "A3"})
        self.assertEqual(first["turno"], "B")
        self.assertTrue(enemy_pairs)
        self.assertTrue(all(next_state["turno"] == "A" for _, next_state in enemy_pairs))
        self.assertEqual(state, original)

    def test_explicit_collection_is_an_action_and_consumes_the_turn(self) -> None:
        state = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 4},
            ],
            queen=(2, 2),
        )
        action, collected = next(
            pair for pair in action_successors(state) if pair[0]["type"] == "collect"
        )

        self.assertEqual(action["unit_id"], "A1")
        self.assertEqual(collected["juego"]["portador_recurso"], "A1")
        self.assertEqual(collected["turno"], "B")


class AdversarialSearchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        with main.lock:
            self.current_state = copy.deepcopy(main.current_state)
            self.source_name = main.source_name

    def tearDown(self) -> None:
        with main.lock:
            main.current_state = self.current_state
            main.source_name = self.source_name

    def sample_state(self) -> dict[str, Any]:
        return make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 0},
                {"id": "A2", "bando": "A", "tipo": "knight", "fila": 1, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 5},
                {"id": "B2", "bando": "B", "tipo": "knight", "fila": 4, "columna": 3},
            ]
        )


    def test_depth_zero_has_no_action_and_positive_depth_counts_full_turns(self) -> None:
        state = self.sample_state()
        for search in (minimax, alpha_beta):
            result_zero = search(state, 0)
            self.assertIsNone(result_zero["action"])
            self.assertEqual(result_zero["depth_reached"], 0)
            self.assertEqual(result_zero["nodes_visited"], 1)
            self.assertEqual(result_zero["nodes_evaluated"], 1)

        for depth in (1, 2, 3):
            with self.subTest(depth=depth):
                result = minimax(state, depth)
                self.assertEqual(result["requested_depth"], depth)
                self.assertEqual(result["depth_reached"], depth)
                self.assertIsNotNone(result["action"])

    def test_minimax_and_alpha_beta_match_value_and_canonical_action(self) -> None:
        state = tactical_state()
        original = copy.deepcopy(state)
        plain = minimax(state, 3)
        pruned = alpha_beta(state, 3)

        self.assertEqual(plain["value"], pruned["value"])
        self.assertEqual(plain["action"], pruned["action"])
        self.assertEqual(state, original)
        self.assertEqual(plain["nodes_pruned"], 0)
        self.assertGreater(pruned["nodes_pruned"], 0)
        self.assertLess(pruned["nodes_visited"], plain["nodes_visited"])
        self.assertLess(pruned["nodes_evaluated"], plain["nodes_evaluated"])

    def test_action_order_changes_pruning_not_the_decision(self) -> None:
        state = tactical_state()
        normal = alpha_beta(state, 3, "normal")
        reverse = alpha_beta(state, 3, "reverse")

        self.assertEqual(normal["value"], reverse["value"])
        self.assertEqual(normal["action"], reverse["action"])
        self.assertNotEqual(normal["nodes_visited"], reverse["nodes_visited"])
        self.assertNotEqual(normal["nodes_pruned"], reverse["nodes_pruned"])
        self.assertEqual(normal["action_order"], "normal")
        self.assertEqual(reverse["action_order"], "reverse")

    def test_depth_changes_from_queen_approach_to_intercepting_capture(self) -> None:
        state = tactical_state()
        depth_one = minimax(state, 1)
        depth_two = minimax(state, 2)
        depth_three = minimax(state, 3)

        self.assertEqual(depth_one["action"]["unit_id"], "A1")
        self.assertEqual(depth_one["action"]["destination"], {"fila": 3, "columna": 3})
        self.assertEqual(depth_two["action"]["unit_id"], "A2")
        self.assertEqual(depth_two["action"]["destination"], {"fila": 3, "columna": 1})
        self.assertEqual(depth_three["action"], depth_two["action"])
        self.assertLess(depth_two["nodes_visited"], depth_three["nodes_visited"])

    def test_intercept_is_better_than_approaching_queen_after_enemy_reply(self) -> None:
        state = tactical_state()
        result = minimax(state, 2)

        intercept = next(
            node
            for action, node in action_successors(state)
            if action["unit_id"] == "A2"
            and action["destination"] == {"fila": 3, "columna": 1}
        )
        approach = next(
            node
            for action, node in action_successors(state)
            if action["unit_id"] == "A1"
            and action["destination"] == {"fila": 3, "columna": 3}
        )
        intercept_worst_reply = min(evaluate(reply, "A") for _, reply in action_successors(intercept))
        approach_worst_reply = min(evaluate(reply, "A") for _, reply in action_successors(approach))

        self.assertEqual(result["action"]["unit_id"], "A2")
        self.assertEqual(result["value"], intercept_worst_reply)
        self.assertGreater(intercept_worst_reply, approach_worst_reply)

    def test_equal_leaf_values_use_canonical_action_independent_of_exploration(self) -> None:
        state = self.sample_state()
        with (
            patch("backend.algorithms.minimax.evaluate", return_value=0.0),
            patch("backend.algorithms.alpha_beta.evaluate", return_value=0.0),
        ):
            plain_normal = minimax(state, 3, "normal")
            plain_reverse = minimax(state, 3, "reverse")
            pruned_normal = alpha_beta(state, 3, "normal")
            pruned_reverse = alpha_beta(state, 3, "reverse")

        self.assertEqual(plain_normal["action"], plain_reverse["action"])
        self.assertEqual(plain_normal["action"], pruned_normal["action"])
        self.assertEqual(plain_normal["action"], pruned_reverse["action"])
        self.assertEqual(plain_normal["value"], 0.0)
        self.assertGreater(pruned_normal["nodes_pruned"], 0)
        self.assertGreater(pruned_reverse["nodes_pruned"], 0)

    def test_terminal_root_is_detected_before_depth_limit(self) -> None:
        state = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 4},
            ],
            carrier="A1",
            queen_spawn=(3, 3),
        )
        result = alpha_beta(state, 3)

        self.assertIsNone(result["action"])
        self.assertEqual(result["value"], 100_000)
        self.assertEqual(result["depth_reached"], 0)
        self.assertEqual(result["nodes_generated"], 0)
        self.assertEqual(result["nodes_evaluated"], 1)

    def test_immediate_victory_beats_all_positional_moves(self) -> None:
        state = make_state(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 0},
                {"id": "A2", "bando": "A", "tipo": "rook", "fila": 2, "columna": 3},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 4},
            ],
            carrier="A1",
            queen_spawn=(3, 3),
        )
        result = minimax(state, 1)

        self.assertEqual(result["value"], 100_000)
        self.assertEqual(result["action"]["unit_id"], "A1")
        self.assertEqual(result["action"]["destination"], {"fila": 0, "columna": 0})

    def test_depth_and_order_validation_is_explicit(self) -> None:
        state = self.sample_state()
        invalid_depths: tuple[Any, ...] = (-1, 1.5, True)
        for depth in invalid_depths:
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                minimax(state, depth)
        with self.assertRaises(ValueError):
            alpha_beta(state, 1, "random")

    async def test_adversarial_api_returns_real_recommendation_without_mutation(self) -> None:
        state = self.sample_state()
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        status, response = await post_json(
            "/api/adversarial",
            {"algorithm": "alpha_beta", "depth": 2, "action_order": "reverse"},
        )
        result = response["result"]
        self.assertEqual(status, 200)
        self.assertEqual(result["algorithm"], "alpha_beta")
        self.assertIn(result["action"], [action for action, _ in action_successors(state)])
        self.assertEqual(result["requested_depth"], 2)
        self.assertIn("nodes_visited", result)
        self.assertIn("nodes_pruned", result)
        self.assertEqual(main.current_state, original)

    async def test_adversarial_test_mode_and_invalid_depth(self) -> None:
        state = self.sample_state()
        state["prueba"] = {"modo": "adversarial"}
        with main.lock:
            main.current_state = copy.deepcopy(state)
        original = copy.deepcopy(main.current_state)

        status, response = await post_json(
            "/api/test",
            {"algorithm": "minimax", "depth": 1, "action_order": "normal"},
        )
        invalid_status, _ = await post_json(
            "/api/adversarial", {"algorithm": "minimax", "depth": -1}
        )
        invalid_test_algorithm, _ = await post_json(
            "/api/test", {"algorithm": "bfs", "depth": 1}
        )
        invalid_config = copy.deepcopy(original)
        invalid_config["juego"]["profundidad_maxima_minimax"] = 1.5
        with main.lock:
            main.current_state = invalid_config
        invalid_config_status, _ = await post_json(
            "/api/adversarial", {"algorithm": "minimax"}
        )
        with main.lock:
            main.current_state = original

        self.assertEqual(status, 200)
        self.assertEqual(response["mode"], "adversarial")
        self.assertEqual(response["result"]["algorithm"], "minimax")
        self.assertEqual(invalid_status, 422)
        self.assertEqual(invalid_test_algorithm, 422)
        self.assertEqual(invalid_config_status, 422)
        self.assertEqual(main.current_state, original)


if __name__ == "__main__":
    unittest.main()