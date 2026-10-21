import copy
import json
import unittest
from typing import Any
from unittest.mock import patch

from starlette.types import Message

from backend import main
from backend.game.engine import (
    apply_move,
    check_status,
    check_winner,
    collect_queen,
    configure_kings,
    generate_kings,
    is_goal,
    state_key,
    successors,
    transition,
)
from backend.game.movement import apply_move as movement_apply_move
from backend.game.validation import ScenarioValidationError, validate_state
from backend.scenarios import prepare_scenario


def make_scenario(
    units: list[dict[str, Any]],
    *,
    rows: int = 6,
    columns: int = 6,
    queen: tuple[int, int] | None = (2, 2),
    walls: set[tuple[int, int]] | None = None,
    kings: dict[str, list[dict[str, Any]]] | None = None,
    turn: str = "A",
    bases: dict[str, tuple[int, int]] | None = None,
    carrier: str | None = None,
    queen_spawn: tuple[int, int] | None = None,
) -> dict[str, Any]:
    walls = walls or set()
    terrain = [["camino" for _ in range(columns)] for _ in range(rows)]
    for row, column in walls:
        terrain[row][column] = "muro"
    bases = bases or {"A": (0, 0), "B": (rows - 1, columns - 1)}
    scenario = {
        "version": "1.0",
        "mapa": {"filas": rows, "columnas": columns},
        "tipos_terreno": {
            "camino": {"costo": 1, "transitable": True},
            "muro": {"transitable": False},
        },
        "terreno": terrain,
        "bases": {
            side: {"fila": position[0], "columna": position[1]}
            for side, position in bases.items()
        },
        "recurso": (
            {"fila": queen[0], "columna": queen[1]} if queen is not None else None
        ),
        "unidades": copy.deepcopy(units),
        "turno": turn,
        "juego": {"portador_recurso": carrier},
    }
    if carrier is None and queen is None:
        raise ValueError("Las pruebas requieren reina en tablero o portador")
    if carrier is not None:
        resource_spawn = queen_spawn or queen or (0, max(0, columns - 1))
        scenario["recurso_spawn"] = {
            "fila": resource_spawn[0],
            "columna": resource_spawn[1],
        }
    if kings is not None:
        scenario["reyes"] = copy.deepcopy(kings)
    return prepare_scenario(scenario)


async def request_json(path: str, body: dict[str, Any], method: str = "POST") -> tuple[int, dict[str, Any]]:
    messages: list[Message] = []
    delivered = False
    encoded = json.dumps(body).encode("utf-8")

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
        "method": method,
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


class EngineTests(unittest.TestCase):
    def test_normal_move_changes_turn_and_starts_game(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        result = apply_move(state, "A1", {"fila": 1, "columna": 2})

        self.assertEqual((result["unidades"][0]["fila"], result["unidades"][0]["columna"]), (1, 2))
        self.assertEqual(result["turno"], "B")
        self.assertEqual(result["juego"]["estado"], "en_curso")
        self.assertIsNone(result["juego"]["resultado"])

    def test_illegal_move_does_not_mutate_state(self) -> None:
        state = make_scenario([{"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1}])
        original = copy.deepcopy(state)

        with self.assertRaisesRegex(ValueError, "no es legal"):
            apply_move(state, "A1", {"fila": 2, "columna": 2})
        self.assertEqual(state, original)

    def test_cannot_move_enemy_unit_or_inactive_unit(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            {"id": "A2", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 2, "activo": False},
        ])
        with self.assertRaisesRegex(ValueError, "no pertenece"):
            apply_move(state, "B1", {"fila": 4, "columna": 3})
        with self.assertRaisesRegex(ValueError, "inactiva"):
            apply_move(state, "A2", {"fila": 0, "columna": 3})

    def test_capture_respawns_when_spawn_is_free(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
        ])
        state["unidades"][1]["spawn"] = {"fila": 3, "columna": 2}
        victim_before = next(unit for unit in state["unidades"] if unit["id"] == "B1")
        self.assertEqual((victim_before["fila"], victim_before["columna"]), (1, 2))
        self.assertEqual(victim_before["spawn"], {"fila": 3, "columna": 2})
        self.assertFalse(
            any(
                unit.get("activo", True) is True
                and (unit["fila"], unit["columna"]) == (3, 2)
                for unit in state["unidades"]
            )
        )
        result = apply_move(state, "A1", {"fila": 1, "columna": 2})
        attacker = next(unit for unit in result["unidades"] if unit["id"] == "A1")
        victim = next(unit for unit in result["unidades"] if unit["id"] == "B1")

        self.assertEqual((attacker["fila"], attacker["columna"]), (1, 2))
        self.assertTrue(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (3, 2))

    def test_capture_leaves_victim_inactive_when_spawn_is_occupied(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 2, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
            {"id": "A2", "bando": "A", "tipo": "estandar", "fila": 3, "columna": 2},
        ], queen=(0, 5))
        state["unidades"][1]["spawn"] = {"fila": 3, "columna": 2}
        state["unidades"][1]["fila"], state["unidades"][1]["columna"] = 2, 2
        result = apply_move(state, "A1", {"fila": 2, "columna": 2})
        victim = next(unit for unit in result["unidades"] if unit["id"] == "B1")

        self.assertFalse(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (-1, -1))
        validate_state(result)

    def test_simultaneous_respawns_use_deterministic_id_order(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
            {"id": "B2", "bando": "B", "tipo": "estandar", "fila": 3, "columna": 3, "activo": False},
            {"id": "B3", "bando": "B", "tipo": "rook", "fila": 4, "columna": 2},
        ], queen=(0, 5))
        captured = next(unit for unit in state["unidades"] if unit["id"] == "B1")
        waiting = next(unit for unit in state["unidades"] if unit["id"] == "B2")
        captured["spawn"] = {"fila": 1, "columna": 1}
        waiting["spawn"] = {"fila": 1, "columna": 1}
        result = apply_move(state, "A1", {"fila": 1, "columna": 2})
        by_id = {unit["id"]: unit for unit in result["unidades"]}

        self.assertTrue(by_id["B1"]["activo"])
        self.assertEqual((by_id["B1"]["fila"], by_id["B1"]["columna"]), (1, 1))
        self.assertFalse(by_id["B2"]["activo"])
        self.assertEqual((by_id["B2"]["fila"], by_id["B2"]["columna"]), (-1, -1))

    def test_inactive_unit_respawns_when_its_spawn_becomes_free(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 3, "columna": 2},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2, "activo": False},
            {"id": "B2", "bando": "B", "tipo": "knight", "fila": 4, "columna": 2},
        ])
        blocker = next(unit for unit in state["unidades"] if unit["id"] == "A1")
        blocker["fila"], blocker["columna"] = 1, 2
        result = apply_move(state, "A1", {"fila": 1, "columna": 3})
        victim = next(unit for unit in result["unidades"] if unit["id"] == "B1")

        self.assertTrue(victim["activo"])
        self.assertEqual((victim["fila"], victim["columna"]), (1, 2))

    def test_capturing_carrier_returns_queen_to_original_spawn(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
        ], queen=None, carrier="B1")
        original_queen_spawn = copy.deepcopy(state["recurso_spawn"])
        original_victim_spawn = copy.deepcopy(state["unidades"][1]["spawn"])
        result = apply_move(state, "A1", {"fila": 1, "columna": 2})
        attacker = next(unit for unit in result["unidades"] if unit["id"] == "A1")
        victim = next(unit for unit in result["unidades"] if unit["id"] == "B1")

        self.assertIsNone(result["juego"]["portador_recurso"])
        self.assertEqual(result["recurso"], original_queen_spawn)
        self.assertEqual(result["recurso_spawn"], original_queen_spawn)
        self.assertNotEqual(result["recurso"], {"fila": 1, "columna": 2})
        self.assertEqual((attacker["fila"], attacker["columna"]), (1, 2))
        self.assertEqual(victim["spawn"], original_victim_spawn)
        validate_state(result)

    def test_normal_queen_pickup_and_explicit_pickup(self) -> None:
        entering = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=(1, 2))
        picked_up = apply_move(entering, "A1", {"fila": 1, "columna": 2})
        self.assertEqual(picked_up["juego"]["portador_recurso"], "A1")
        self.assertIsNone(picked_up["recurso"])

        standing = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=(2, 2))
        collected = collect_queen(standing, "A1")
        self.assertEqual(collected["juego"]["portador_recurso"], "A1")
        self.assertIsNone(collected["recurso"])
        self.assertEqual(collected["turno"], "B")
        self.assertEqual((collected["unidades"][0]["fila"], collected["unidades"][0]["columna"]), (2, 2))

    def test_capturing_a_moved_carrier_does_not_move_queen_spawn(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=(1, 2))
        queen_spawn = copy.deepcopy(state["recurso_spawn"])

        carrier = apply_move(state, "A1", {"fila": 1, "columna": 2})
        blocker_move = apply_move(carrier, "B1", {"fila": 4, "columna": 3})
        moved_carrier = apply_move(blocker_move, "A1", {"fila": 1, "columna": 3})
        captured = apply_move(moved_carrier, "B1", {"fila": 1, "columna": 3})

        self.assertEqual(captured["recurso_spawn"], queen_spawn)
        self.assertEqual(captured["recurso"], queen_spawn)
        self.assertNotEqual(captured["recurso"], {"fila": 1, "columna": 3})
        validate_state(captured)

    def test_explicit_pickup_is_rejected_while_in_check(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 3, "columna": 0},
        ], queen=(0, 1), kings={"A": [{"fila": 3, "columna": 3}], "B": []})
        self.assertTrue(check_status(state)["A"])
        with self.assertRaisesRegex(ValueError, "jaque"):
            collect_queen(state, "A1")

    def test_carrier_keeps_queen_when_later_move_leaves_king_in_check(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 3, "columna": 0},
        ], queen=None, carrier="A1", kings={"A": [{"fila": 3, "columna": 3}], "B": []})
        result = apply_move(state, "A1", {"fila": 1, "columna": 2})

        self.assertEqual(result["juego"]["portador_recurso"], "A1")
        self.assertIsNone(result["recurso"])
        self.assertTrue(check_status(result)["A"])

    def test_winning_move_and_rejection_after_finalization(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 0, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=None, carrier="A1")
        result = apply_move(state, "A1", {"fila": 0, "columna": 0})

        self.assertEqual(result["juego"]["estado"], "finalizado")
        self.assertEqual(result["juego"]["resultado"], "A")
        self.assertEqual(check_winner(result), "A")
        self.assertTrue(is_goal(result, {"bando": "A"}))
        with self.assertRaisesRegex(ValueError, "finalizado"):
            apply_move(result, "A1", {"fila": 0, "columna": 1})

    def test_explicit_collection_counts_as_a_legal_action_for_draw_detection(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=(2, 2), walls={(1, 2), (3, 2), (2, 1), (2, 3)})
        state["juego"]["estado"] = "en_curso"

        self.assertEqual(check_winner(state), None)
        self.assertTrue(any(
            successor["juego"]["portador_recurso"] == "A1"
            for successor in successors(state)
        ))

    def test_no_legal_action_ends_in_draw(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 0, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 2},
        ], rows=5, columns=5, queen=(4, 0), walls={(1, 2), (3, 2), (2, 1), (2, 3)})
        result = apply_move(state, "A1", {"fila": 0, "columna": 2})

        self.assertEqual(result["juego"]["estado"], "finalizado")
        self.assertEqual(result["juego"]["resultado"], "empate")
        self.assertEqual(check_winner(result), "empate")

    def test_king_configuration_that_blocks_all_actions_finishes_in_a_draw(self) -> None:
        state = make_scenario(
            [
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 3},
            ],
            rows=5,
            columns=5,
            queen=(0, 4),
        )

        configured = configure_kings(
            state,
            {
                "A": [
                    {"id": "KA1", "fila": 1, "columna": 2},
                    {"id": "KA2", "fila": 3, "columna": 2},
                ],
                "B": [
                    {"id": "KB1", "fila": 2, "columna": 1},
                    {"id": "KB2", "fila": 2, "columna": 3},
                ],
            },
        )

        self.assertEqual(
            (configured["juego"]["estado"], configured["juego"]["resultado"]),
            ("finalizado", "empate"),
        )
        self.assertEqual(successors(configured), [])

    def test_manual_and_automatic_king_configuration(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            {"id": "A_SLEEP", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 3, "activo": False},
        ])
        manual = configure_kings(state, {
            "A": [{"id": "KA", "fila": 0, "columna": 2}],
            "B": [{"id": "KB", "fila": 5, "columna": 3}],
        })
        self.assertEqual(len(manual["reyes"]["A"]), 1)
        with self.assertRaises(ScenarioValidationError):
            configure_kings(state, {"A": [{"fila": 0, "columna": 0}], "B": []})

        auto = generate_kings(state, {"A": 1, "B": 2})
        self.assertEqual((len(auto["reyes"]["A"]), len(auto["reyes"]["B"])), (1, 2))
        self.assertEqual(state_key(auto), state_key(generate_kings(state, {"A": 1, "B": 2})))
        for group in auto["reyes"].values():
            for king in group:
                self.assertTrue(0 <= king["fila"] < state["mapa"]["filas"])
                self.assertTrue(0 <= king["columna"] < state["mapa"]["columnas"])
                self.assertNotEqual((king["fila"], king["columna"]), (0, 3))

    def test_king_configuration_rejects_inactive_unit_spawn(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            {"id": "B_SLEEP", "bando": "B", "tipo": "estandar", "fila": 0, "columna": 3, "activo": False},
        ])

        with self.assertRaisesRegex(ScenarioValidationError, "spawn"):
            configure_kings(state, {"A": [{"fila": 0, "columna": 3}], "B": []})

    def test_greedy_king_generation_fails_atomically_when_counts_do_not_fit(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        original = copy.deepcopy(state)

        with self.assertRaisesRegex(ValueError, "No hay suficientes posiciones"):
            generate_kings(state, {"A": 20, "B": 20})
        self.assertEqual(state, original)

    def test_kings_cannot_be_changed_after_first_action(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        started = apply_move(state, "A1", {"fila": 1, "columna": 2})
        with self.assertRaisesRegex(ValueError, "antes de iniciar"):
            configure_kings(started, {"A": [], "B": []})

    def test_state_key_is_order_independent_for_equivalent_units(self) -> None:
        state = make_scenario([
            {"id": "A2", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        reordered = copy.deepcopy(state)
        reordered["unidades"].reverse()
        self.assertEqual(state_key(state), state_key(reordered))

    def test_successors_cover_every_active_unit_without_mutating_input(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "A2", "bando": "A", "tipo": "knight", "fila": 1, "columna": 3},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        original = copy.deepcopy(state)
        next_states = successors(state)

        self.assertGreater(len(next_states), 2)
        self.assertEqual(state, original)
        self.assertTrue(all(next_state is not state for next_state in next_states))

    def test_successors_propagates_transition_contradictions(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])

        with (
            patch("backend.game.engine.transition", side_effect=ValueError("motor inconsistente")),
            self.assertRaisesRegex(ValueError, "motor inconsistente"),
        ):
            successors(state)

    def test_transition_skips_unchanged_base_connectivity_check(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])

        with patch(
            "backend.game.validation._base_positions_connected",
            side_effect=AssertionError("static connectivity must not be recomputed"),
        ):
            result = apply_move(state, "A1", {"fila": 1, "columna": 2})
        self.assertEqual(result["turno"], "B")

    def test_successors_include_explicit_queen_collection(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=(2, 2))
        original = copy.deepcopy(state)
        next_states = successors(state)

        self.assertTrue(any(
            result["juego"]["portador_recurso"] == "A1"
            and (result["unidades"][0]["fila"], result["unidades"][0]["columna"]) == (2, 2)
            for result in next_states
        ))
        self.assertEqual(state, original)

    def test_transition_and_apply_move_are_pure_and_consistent(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        original = copy.deepcopy(state)
        via_transition = transition(state, {
            "type": "move", "unit_id": "A1", "destination": {"fila": 1, "columna": 2}
        })
        via_wrapper = apply_move(state, "A1", {"fila": 1, "columna": 2})
        via_legacy_wrapper = movement_apply_move(state, "A1", {"fila": 1, "columna": 2})

        self.assertEqual(state, original)
        self.assertEqual(via_transition, via_wrapper)
        self.assertEqual(via_transition, via_legacy_wrapper)
        self.assertIsNot(via_transition, state)
        self.assertIsNot(via_transition["unidades"], state["unidades"])

    def test_initial_scenario_is_prepared(self) -> None:
        self.assertEqual(main.initial_state["juego"]["estado"], "configuracion")
        self.assertIsNone(main.initial_state["juego"]["resultado"])
        self.assertTrue(all("spawn" in unit for unit in main.initial_state["unidades"]))

    def test_validate_state_accepts_queen_reset_to_original_spawn_after_capture(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
        ], queen=None, carrier="B1")
        captured = apply_move(state, "A1", {"fila": 1, "columna": 2})
        validate_state(captured)
        self.assertEqual(captured["recurso"], captured["recurso_spawn"])


class EngineApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        with main.lock:
            self.initial_state = copy.deepcopy(main.initial_state)
            self.current_state = copy.deepcopy(main.current_state)
            self.source_name = main.source_name

    def tearDown(self) -> None:
        with main.lock:
            main.initial_state = self.initial_state
            main.current_state = self.current_state
            main.source_name = self.source_name

    async def test_failed_move_preserves_official_state_and_returns_422(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)
        status, error = await request_json("/api/move", {
            "unit_id": "A1", "destination": {"row": 2, "column": 2}
        })
        state_status, current = await request_json("/api/state", {}, method="GET")

        self.assertEqual(status, 422)
        self.assertIn("legal", str(error["detail"]))
        self.assertEqual(state_status, 200)
        self.assertEqual(current["state"], state)

    async def test_collect_endpoint_and_reset_restore_initial_scenario(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ], queen=(2, 2))
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)
        status, response = await request_json("/api/collect", {"unit_id": "A1"})
        self.assertEqual(status, 200)
        self.assertEqual(response["state"]["juego"]["portador_recurso"], "A1")

        reset_status, reset_response = await request_json("/api/reset", {})
        self.assertEqual(reset_status, 200)
        self.assertEqual(reset_response["state"], state)

    async def test_king_configuration_endpoint_supports_automatic_mode(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)
        status, response = await request_json("/api/kings", {
            "mode": "automatic", "counts": {"A": 1, "B": 2}
        })

        self.assertEqual(status, 200)
        self.assertEqual(len(response["state"]["reyes"]["A"]), 1)
        self.assertEqual(len(response["state"]["reyes"]["B"]), 2)

    async def test_king_configuration_endpoint_is_atomic(self) -> None:
        state = make_scenario([
            {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
        ])
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)
        status, response = await request_json("/api/kings", {
            "mode": "manual", "kings": {"A": [{"row": 0, "column": 0}], "B": []}
        })
        self.assertEqual(status, 422)
        self.assertIn("base", str(response["detail"]))
        with main.lock:
            self.assertEqual(main.current_state, state)


if __name__ == "__main__":
    unittest.main()
