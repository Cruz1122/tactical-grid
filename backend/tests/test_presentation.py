import copy
import json
import unittest
from typing import Any

from fastapi import HTTPException
from starlette.types import Message

from backend import main
from backend.game.engine import apply_move
from backend.game.presentation import (
    build_presentation,
    state_revision,
    transition_events,
)
from backend.scenarios import prepare_scenario


def make_state(
    *,
    units: list[dict[str, Any]],
    queen: tuple[int, int] = (3, 3),
    turn: str = "A",
    kings: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    terrain = [["camino" for _ in range(5)] for _ in range(5)]
    scenario: dict[str, Any] = {
        "version": "1.0",
        "mapa": {"filas": 5, "columnas": 5},
        "tipos_terreno": {
            "camino": {"costo": 1, "transitable": True},
        },
        "terreno": terrain,
        "bases": {
            "A": {"fila": 0, "columna": 0},
            "B": {"fila": 4, "columna": 4},
        },
        "recurso": {"fila": queen[0], "columna": queen[1]},
        "unidades": copy.deepcopy(units),
        "turno": turn,
        "juego": {"portador_recurso": None},
    }
    if kings is not None:
        scenario["reyes"] = copy.deepcopy(kings)
    return prepare_scenario(scenario)


async def request_get(path: str, query: str = "") -> tuple[int, dict[str, Any]]:
    messages: list[Message] = []
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query.encode("ascii"),
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "root_path": "",
    }
    await main.app(scope, receive, send)
    status = next(
        message["status"]
        for message in messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status, json.loads(body)


class PresentationProjectionTests(unittest.TestCase):
    def test_projection_is_derived_without_mutating_official_state(self) -> None:
        state = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 3},
            ],
            queen=(2, 2),
            kings={"A": [{"id": "KA", "fila": 1, "columna": 1}], "B": []},
        )
        original = copy.deepcopy(state)

        presentation = build_presentation(state)

        self.assertEqual(state, original)
        self.assertIn("revision", presentation)
        self.assertEqual(presentation["recogida_autorizada"]["A1"], True)
        self.assertEqual(presentation["recogida_autorizada"]["B1"], False)
        self.assertEqual(presentation["eventos_ultimo_turno"], [])

    def test_events_confirm_capture_and_respawn(self) -> None:
        before = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
            ]
        )
        victim = next(unit for unit in before["unidades"] if unit["id"] == "B1")
        victim["spawn"] = {"fila": 3, "columna": 2}
        after = apply_move(before, "A1", {"fila": 1, "columna": 2})

        events = transition_events(before, after)

        self.assertEqual(
            [(event["tipo"], event.get("victima_id"), event.get("unidad_id")) for event in events[:2]],
            [("captura", "B1", None), ("reaparicion", None, "B1")],
        )
        self.assertEqual(events[0]["posicion"], {"fila": 1, "columna": 2})
        self.assertEqual(events[1]["posicion"], {"fila": 3, "columna": 2})

    def test_events_confirm_queen_drop_when_carrier_is_captured(self) -> None:
        before = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 2},
                {"id": "B2", "bando": "B", "tipo": "estandar", "fila": 4, "columna": 3},
            ],
            queen=(3, 3),
            turn="A",
        )
        before["recurso"] = None
        before["juego"]["portador_recurso"] = "B1"

        after = apply_move(before, "A1", {"fila": 1, "columna": 2})

        dropped = next(event for event in transition_events(before, after) if event["tipo"] == "recurso_suelto")
        self.assertEqual(dropped["posicion"], {"fila": 3, "columna": 3})
        self.assertEqual(after["recurso"], {"fila": 3, "columna": 3})
        self.assertIsNone(after["juego"]["portador_recurso"])


class LegalMovesApiTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_classifies_normal_and_capture_destinations(self) -> None:
        state = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 1, "columna": 3},
            ]
        )
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)

        status, response = await request_get("/api/legal-moves", "unit_id=A1")

        self.assertEqual(status, 200)
        self.assertTrue(response["allowed"])
        self.assertIn({"row": 1, "column": 2}, response["normal"])
        self.assertIn({"row": 1, "column": 3}, response["captures"])
        self.assertEqual(
            next(item for item in response["destinations"] if item["column"] == 3)["kind"],
            "capture",
        )
        self.assertEqual(response["presentation"]["revision"], state_revision(state))

    async def test_turn_and_terminal_state_return_empty_destinations(self) -> None:
        state = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 3, "columna": 3},
            ],
            turn="B",
        )
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)

        status, response = await request_get("/api/legal-moves", "unit_id=A1")
        self.assertEqual(status, 200)
        self.assertFalse(response["allowed"])
        self.assertEqual(response["reason"], "turno")
        self.assertEqual(response["destinations"], [])

        state["juego"]["estado"] = "finalizado"
        state["juego"]["resultado"] = "empate"
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)
        status, response = await request_get("/api/legal-moves", "unit_id=B1")
        self.assertEqual(status, 200)
        self.assertFalse(response["allowed"])
        self.assertEqual(response["reason"], "finalizado")
        self.assertEqual(response["destinations"], [])

    async def test_unit_sharing_dropped_queen_can_collect_on_its_turn(self) -> None:
        state = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            ],
            queen=(2, 2),
            turn="A",
        )
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)

        status, response = await request_get("/api/legal-moves", "unit_id=A1")

        self.assertEqual(status, 200)
        self.assertTrue(response["collect_allowed"])
        self.assertTrue(response["presentation"]["recogida_autorizada"]["A1"])
        self.assertIn(
            {
                "row": 2,
                "column": 2,
                "fila": 2,
                "columna": 2,
                "kind": "collect",
            },
            response["destinations"],
        )

    async def test_capture_of_carrier_at_queen_spawn_exposes_pickup_on_next_turn(self) -> None:
        before = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 1, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 2, "columna": 2},
                {"id": "B2", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            ],
            queen=(2, 2),
            turn="A",
        )
        before["recurso"] = None
        before["juego"]["portador_recurso"] = "B1"

        after_capture = apply_move(before, "A1", {"fila": 2, "columna": 2})
        self.assertEqual(after_capture["recurso"], {"fila": 2, "columna": 2})
        self.assertEqual(after_capture["turno"], "B")

        after_defender = apply_move(after_capture, "B2", {"fila": 4, "columna": 3})
        self.assertEqual(after_defender["turno"], "A")
        with main.lock:
            main.initial_state = copy.deepcopy(after_defender)
            main.current_state = copy.deepcopy(after_defender)

        status, response = await request_get("/api/legal-moves", "unit_id=A1")

        self.assertEqual(status, 200)
        self.assertTrue(response["allowed"])
        self.assertTrue(response["collect_allowed"])
        self.assertEqual(
            [item["kind"] for item in response["destinations"] if item["fila"] == 2 and item["columna"] == 2],
            ["collect"],
        )

    def test_stale_revision_rejects_move_without_mutating_state(self) -> None:
        state = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "rook", "fila": 1, "columna": 1},
                {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 3, "columna": 3},
            ]
        )
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)

        request = main.MoveRequest(
            unit_id="A1",
            destination=main.Position(row=1, column=2),
            revision="stale-revision",
        )
        with self.assertRaises(HTTPException) as raised:
            main.move(request)

        self.assertEqual(raised.exception.status_code, 409)
        with main.lock:
            self.assertEqual(main.current_state, state)

    def test_stale_revision_rejects_collect_without_mutating_state(self) -> None:
        state = make_state(
            units=[
                {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2},
                {"id": "B1", "bando": "B", "tipo": "rook", "fila": 4, "columna": 4},
            ],
            queen=(2, 2),
        )
        with main.lock:
            main.initial_state = copy.deepcopy(state)
            main.current_state = copy.deepcopy(state)

        request = main.CollectRequest(unit_id="A1", revision="stale-revision")
        with self.assertRaises(HTTPException) as raised:
            main.collect(request)

        self.assertEqual(raised.exception.status_code, 409)
        with main.lock:
            self.assertEqual(main.current_state, state)


if __name__ == "__main__":
    unittest.main()
