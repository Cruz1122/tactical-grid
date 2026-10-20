import copy
import json
import unittest
from pathlib import Path
from typing import Any

from starlette.types import Message

from backend import main
from backend.game.validation import (
    ScenarioValidationError,
    validate_scenario,
    validate_state,
)
from backend.scenarios import prepare_scenario


def valid_scenario() -> dict[str, Any]:
    return {
        "version": "1.0",
        "mapa": {"filas": 4, "columnas": 4},
        "tipos_terreno": {
            "camino": {"costo": 1, "transitable": True},
            "muro": {"transitable": False},
        },
        "terreno": [
            ["camino", "camino", "camino", "camino"],
            ["camino", "muro", "camino", "camino"],
            ["camino", "camino", "camino", "camino"],
            ["camino", "camino", "camino", "camino"],
        ],
        "bases": {
            "A": {"fila": 0, "columna": 0},
            "B": {"fila": 3, "columna": 3},
        },
        "recurso": {"fila": 2, "columna": 2},
        "unidades": [
            {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 1},
            {"id": "B1", "bando": "B", "tipo": "knight", "fila": 3, "columna": 2},
        ],
        "turno": "A",
        "juego": {"portador_recurso": None},
        "datos_extra": {"mantener": True},
    }


async def request_json(
    path: str,
    body: bytes = b"",
    method: str = "POST",
    content_type: str = "application/json",
) -> tuple[int, dict[str, Any]]:
    messages: list[Message] = []
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    headers = [(b"content-type", content_type.encode("ascii"))] if body else []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
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


class ScenarioValidationTests(unittest.TestCase):
    def assert_invalid(self, scenario: dict[str, Any], message: str) -> None:
        with self.assertRaises(ScenarioValidationError) as raised:
            validate_scenario(scenario)
        self.assertIn(message, str(raised.exception))

    def test_valid_scenario_prepares_spawn_and_preserves_input(self) -> None:
        scenario = valid_scenario()
        original = copy.deepcopy(scenario)
        state = prepare_scenario(scenario)

        self.assertEqual(scenario, original)
        self.assertEqual(state["unidades"][0]["spawn"], {"fila": 0, "columna": 1})
        self.assertEqual(state["recurso_spawn"], {"fila": 2, "columna": 2})
        self.assertTrue(state["unidades"][0]["activo"])
        self.assertEqual(state["datos_extra"], {"mantener": True})
        validate_state(state)

    def test_existing_initial_scenario_is_valid(self) -> None:
        scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "initial.json"
        state = prepare_scenario(json.loads(scenario_path.read_text(encoding="utf-8")))
        self.assertEqual((state["mapa"]["filas"], state["mapa"]["columnas"]), (20, 20))

    def test_supported_unit_types_and_legacy_names_are_accepted(self) -> None:
        scenario = valid_scenario()
        types = ["estandar", "knight", "rook", "bishop", "caballo", "torre", "alfil"]
        positions = [(0, 1), (3, 2), (0, 2), (3, 1), (1, 0), (1, 2), (2, 3)]
        scenario["unidades"] = [
            {
                "id": f"U{index}",
                "bando": "A" if index % 2 == 0 else "B",
                "tipo": unit_type,
                "fila": row,
                "columna": column,
            }
            for index, (unit_type, (row, column)) in enumerate(zip(types, positions))
        ]
        validate_scenario(scenario)

    def test_inconsistent_dimensions_are_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["terreno"].pop()
        self.assert_invalid(scenario, "mapa.filas")

    def test_unknown_terrain_is_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["terreno"][0][0] = "lava"
        self.assert_invalid(scenario, "tipo de terreno desconocido")

    def test_negative_walkable_cost_is_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["tipos_terreno"]["camino"]["costo"] = -1
        self.assert_invalid(scenario, "debe ser un número positivo")

    def test_non_finite_json_numbers_are_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["datos_extra"]["valor"] = float("nan")
        self.assert_invalid(scenario, "los números JSON deben ser finitos")

    def test_position_outside_map_is_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["unidades"][0]["fila"] = 4
        self.assert_invalid(scenario, "fuera del mapa")

    def test_unit_on_obstacle_is_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["unidades"][0]["fila"] = 1
        scenario["unidades"][0]["columna"] = 1
        self.assert_invalid(scenario, "está sobre un obstáculo")

    def test_duplicate_unit_ids_are_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["unidades"][1]["id"] = scenario["unidades"][0]["id"]
        self.assert_invalid(scenario, "identificador repetido")

    def test_invalid_turn_is_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["turno"] = "C"
        self.assert_invalid(scenario, "turno: debe ser 'A' o 'B'")

    def test_missing_carrier_is_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["juego"]["portador_recurso"] = "A99"
        self.assert_invalid(scenario, "unidad inexistente")

    def test_overlapping_active_units_are_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["unidades"][1]["fila"] = scenario["unidades"][0]["fila"]
        scenario["unidades"][1]["columna"] = scenario["unidades"][0]["columna"]
        self.assert_invalid(scenario, "se superpone con la unidad activa")

    def test_scenario_without_kings_is_valid(self) -> None:
        scenario = valid_scenario()
        validate_scenario(scenario)
        self.assertNotIn("reyes", prepare_scenario(scenario))

    def test_kings_on_bases_are_rejected(self) -> None:
        scenario = valid_scenario()
        scenario["reyes"] = {
            "A": [{"id": "KA", "fila": 0, "columna": 0}],
            "B": [],
        }
        self.assert_invalid(scenario, "un rey no puede ocupar una base")

    def test_carrier_and_resource_position_must_match(self) -> None:
        scenario = valid_scenario()
        scenario["juego"]["portador_recurso"] = "A1"
        self.assert_invalid(scenario, "debe ser null o coincidir")

    def test_carrier_without_current_resource_requires_original_spawn(self) -> None:
        scenario = valid_scenario()
        scenario["juego"]["portador_recurso"] = "A1"
        scenario["recurso"] = None
        self.assert_invalid(scenario, "recurso_spawn")

    def test_uncarried_resource_spawn_cannot_contradict_initial_resource(self) -> None:
        scenario = valid_scenario()
        scenario["recurso_spawn"] = {"fila": 0, "columna": 3}
        self.assert_invalid(scenario, "debe coincidir con la posición inicial de recurso")


class ScenarioApiTests(unittest.IsolatedAsyncioTestCase):
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

    def test_openapi_documents_file_upload(self) -> None:
        operation = main.app.openapi()["paths"]["/api/scenarios"]["post"]
        content = operation["requestBody"]["content"]

        self.assertEqual(set(content), {"multipart/form-data"})
        self.assertEqual(
            content["multipart/form-data"]["schema"]["properties"]["file"]["format"],
            "binary",
        )

    async def test_json_file_upload_loads_scenario(self) -> None:
        boundary = "ScenarioUploadBoundary"
        uploaded_json = json.dumps(valid_scenario()).encode("utf-8")
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("ascii"),
                b'Content-Disposition: form-data; name="file"; filename="escenario.json"\r\n',
                b"Content-Type: application/json\r\n\r\n",
                uploaded_json,
                f"\r\n--{boundary}--\r\n".encode("ascii"),
            ]
        )
        status, response = await request_json(
            "/api/scenarios",
            body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )

        self.assertEqual(status, 200)
        self.assertEqual(response["source"], "escenario.json")
        self.assertEqual(response["message"], "Escenario cargado correctamente")

    async def test_invalid_json_file_returns_422_in_spanish(self) -> None:
        boundary = "ScenarioUploadBoundary"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("ascii"),
                b'Content-Disposition: form-data; name="file"; filename="roto.json"\r\n',
                b"Content-Type: application/json\r\n\r\n",
                b"{broken",
                f"\r\n--{boundary}--\r\n".encode("ascii"),
            ]
        )
        status, response = await request_json(
            "/api/scenarios",
            body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )

        self.assertEqual(status, 422)
        self.assertEqual(response["detail"], "El archivo adjunto no contiene JSON válido.")

    async def test_malformed_json_returns_422(self) -> None:
        status, response = await request_json("/api/scenarios", b"{broken")
        self.assertEqual(status, 422)
        self.assertEqual(response["detail"], "El cuerpo de la solicitud no contiene JSON válido.")

    async def test_failed_load_preserves_official_state(self) -> None:
        valid_status, loaded = await request_json(
            "/api/scenarios", json.dumps(valid_scenario()).encode("utf-8")
        )
        self.assertEqual(valid_status, 200)
        self.assertTrue(loaded["ok"])
        self.assertEqual(loaded["message"], "Escenario cargado correctamente")

        invalid = valid_scenario()
        invalid["turno"] = "C"
        invalid_status, error = await request_json(
            "/api/scenarios", json.dumps(invalid).encode("utf-8")
        )
        state_status, current = await request_json("/api/state", method="GET")

        self.assertEqual(invalid_status, 422)
        self.assertEqual(state_status, 200)
        self.assertIn("turno", str(error["detail"]))
        self.assertEqual(current["state"], loaded["state"])
        self.assertEqual(current["source"], loaded["source"])


class ScenarioBankApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        with main.lock:
            self.initial_state = copy.deepcopy(main.initial_state)
            self.current_state = copy.deepcopy(main.current_state)
            self.source_name = main.source_name
        self.bank_path = Path(__file__).resolve().parents[2] / "scenarios" / "test_bank"
        self.manifest = json.loads((self.bank_path / "manifest.json").read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        with main.lock:
            main.initial_state = self.initial_state
            main.current_state = self.current_state
            main.source_name = self.source_name

    def test_bank_has_expected_case_distribution(self) -> None:
        results = [case["resultado_esperado"] for case in self.manifest]
        self.assertEqual(results.count("ACEPTAR"), 16)
        self.assertEqual(results.count("RECHAZAR_422"), 66)
        self.assertEqual(results.count("POR_DEFINIR"), 7)

    async def test_all_valid_bank_scenarios_load(self) -> None:
        cases = [case for case in self.manifest if case["resultado_esperado"] == "ACEPTAR"]
        for case in cases:
            with self.subTest(scenario=case["archivo"]):
                scenario_path = self.bank_path / case["archivo"]
                status, response = await request_json(
                    "/api/scenarios", scenario_path.read_bytes()
                )
                self.assertEqual(status, 200, response)
                self.assertTrue(response["ok"])

    async def test_all_invalid_bank_scenarios_reject_atomically(self) -> None:
        cases = [case for case in self.manifest if case["resultado_esperado"] == "RECHAZAR_422"]
        baseline_path = self.bank_path / "valid" / "01_profesor_4x4.json"

        for case in cases:
            with self.subTest(scenario=case["archivo"]):
                baseline_status, baseline = await request_json(
                    "/api/scenarios", baseline_path.read_bytes()
                )
                self.assertEqual(baseline_status, 200)

                scenario_path = self.bank_path / case["archivo"]
                body = scenario_path.read_bytes()
                if not case["clasificacion"].endswith("/syntax"):
                    body = json.dumps(json.loads(body)).encode("utf-8")

                status, response = await request_json("/api/scenarios", body)
                state_status, current = await request_json("/api/state", method="GET")

                self.assertEqual(status, 422, response)
                self.assertEqual(state_status, 200)
                self.assertEqual(current["state"], baseline["state"])
                self.assertEqual(current["source"], baseline["source"])
