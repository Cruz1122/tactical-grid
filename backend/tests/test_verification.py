import copy
import unittest

from backend.algorithms.minimax import minimax
from backend.algorithms.verification import (
    verify_decision,
    verify_path,
    verify_state,
)
from backend.main import Position, SearchRequest, search_state
from backend.tests.test_search import make_state, post_json


class VerificationTests(unittest.TestCase):
    def test_path_is_replayed_step_by_step_and_detects_tampering(self) -> None:
        state = make_state("estandar", (2, 1), rows=5, columns=5)
        original = copy.deepcopy(state)
        result = search_state(
            state,
            SearchRequest(
                algorithm="ucs",
                unit_id="A1",
                goal=Position(row=2, column=3),
            ),
        )

        verified = verify_path(state, result)

        self.assertTrue(verified["valid"], verified)
        self.assertEqual(verified["observed_moves"], 2)
        self.assertEqual(verified["observed_cost"], 2.0)
        self.assertEqual(state, original)

        bad_cost = copy.deepcopy(result)
        bad_cost["cost"] += 1
        self.assertFalse(verify_path(state, bad_cost)["valid"])

        illegal_step = copy.deepcopy(result)
        illegal_step["path"][1] = {"fila": 4, "columna": 4}
        self.assertFalse(verify_path(state, illegal_step)["valid"])

    def test_negative_path_result_states_its_verification_limit(self) -> None:
        state = make_state("bishop", (1, 1), rows=5, columns=5)
        result = search_state(
            state,
            SearchRequest(
                algorithm="bfs",
                unit_id="A1",
                goal=Position(row=1, column=2),
            ),
        )

        verified = verify_path(state, result)

        self.assertFalse(result["found"])
        self.assertTrue(verified["valid"], verified)
        self.assertIn("No se certifica inalcanzabilidad", verified["limitation"])

    def test_state_validation_reports_errors_without_mutation(self) -> None:
        state = make_state()
        valid = verify_state(state)
        self.assertTrue(valid["valid"], valid)

        invalid = copy.deepcopy(state)
        invalid["turno"] = "C"
        original = copy.deepcopy(invalid)
        checked = verify_state(invalid)

        self.assertFalse(checked["valid"])
        self.assertTrue(checked["checks"]["input_unchanged"])
        self.assertEqual(invalid, original)

    def test_decision_is_recomputed_and_tampering_is_rejected(self) -> None:
        state = make_state(
            "estandar",
            (2, 1),
            rows=5,
            columns=5,
            enemies=[
                {
                    "id": "B1",
                    "bando": "B",
                    "tipo": "estandar",
                    "fila": 3,
                    "columna": 3,
                }
            ],
        )
        result = minimax(state, 1)

        verified = verify_decision(state, result)

        self.assertTrue(verified["valid"], verified)
        altered = copy.deepcopy(result)
        altered["value"] += 1
        self.assertFalse(verify_decision(state, altered)["valid"])


class VerificationApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_endpoint_no_longer_returns_not_implemented(self) -> None:
        status, response = await post_json(
            "/api/verify", {"kind": "state", "result": None}
        )

        self.assertEqual(status, 200, response)
        self.assertTrue(response["result"]["valid"], response)


if __name__ == "__main__":
    unittest.main()
