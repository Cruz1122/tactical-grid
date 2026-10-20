import copy
import unittest
from typing import Any

from backend.game.costs import terrain_cost as compatibility_terrain_cost
from backend.game.movement import is_in_check, legal_moves, move_cost, terrain_cost


def make_state(
    *,
    rows: int = 7,
    columns: int = 7,
    units: list[dict[str, Any]] | None = None,
    walls: set[tuple[int, int]] | None = None,
    special_terrain: dict[tuple[int, int], str] | None = None,
    queen: tuple[int, int] | None = None,
    kings: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    walls = walls or set()
    special_terrain = special_terrain or {}
    terrain = [["camino" for _ in range(columns)] for _ in range(rows)]
    for row, column in walls:
        terrain[row][column] = "muro"
    for (row, column), terrain_id in special_terrain.items():
        terrain[row][column] = terrain_id

    return {
        "mapa": {"filas": rows, "columnas": columns},
        "tipos_terreno": {
            "camino": {"costo": 1, "transitable": True},
            "bosque": {"costo": 4, "transitable": True},
            "pantano": {"costo": 2, "transitable": True},
            "muro": {"transitable": False},
        },
        "terreno": terrain,
        "unidades": units or [],
        "reyes": kings or {"A": [], "B": []},
        "recurso": (
            {"fila": queen[0], "columna": queen[1]} if queen is not None else None
        ),
        "juego": {"portador_recurso": None},
    }


def destinations(state: dict[str, Any], unit_id: str) -> set[tuple[int, int]]:
    return {
        (position["fila"], position["columna"])
        for position in legal_moves(state, unit_id)
    }


class MovementTests(unittest.TestCase):
    def test_knight_at_edge_stays_in_bounds_and_jumps_blockers(self) -> None:
        state = make_state(
            units=[
                {"id": "N", "bando": "A", "tipo": "knight", "fila": 0, "columna": 0},
                {"id": "ally", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 1},
            ],
            walls={(1, 0)},
        )

        self.assertEqual(destinations(state, "N"), {(1, 2), (2, 1)})

    def test_rook_stops_before_wall(self) -> None:
        state = make_state(
            units=[{"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 1}],
            walls={(3, 3)},
        )

        moves = destinations(state, "R")
        self.assertIn((3, 2), moves)
        self.assertNotIn((3, 3), moves)
        self.assertNotIn((3, 4), moves)

    def test_bishop_cannot_capture_or_pass_own_unit(self) -> None:
        state = make_state(
            units=[
                {"id": "B", "bando": "A", "tipo": "bishop", "fila": 3, "columna": 1},
                {"id": "ally", "bando": "A", "tipo": "estandar", "fila": 4, "columna": 2},
            ]
        )

        moves = destinations(state, "B")
        self.assertNotIn((4, 2), moves)
        self.assertNotIn((5, 3), moves)

    def test_rook_can_capture_enemy_but_cannot_move_beyond_it(self) -> None:
        state = make_state(
            units=[
                {"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 1},
                {"id": "enemy", "bando": "B", "tipo": "estandar", "fila": 3, "columna": 3},
            ]
        )

        moves = destinations(state, "R")
        self.assertIn((3, 3), moves)
        self.assertNotIn((3, 4), moves)

    def test_king_is_neither_a_destination_nor_a_square_to_pass(self) -> None:
        state = make_state(
            units=[{"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 1}],
            kings={"A": [{"fila": 3, "columna": 3}], "B": []},
        )

        moves = destinations(state, "R")
        self.assertNotIn((3, 3), moves)
        self.assertNotIn((3, 4), moves)

    def test_standard_cannot_move_diagonally_or_off_board(self) -> None:
        state = make_state(
            rows=2,
            columns=2,
            units=[{"id": "S", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0}],
        )

        self.assertEqual(destinations(state, "S"), {(0, 1), (1, 0)})
        with self.assertRaises(ValueError):
            move_cost(state, "S", {"fila": 1, "columna": 1})
        with self.assertRaises(ValueError):
            move_cost(state, "S", {"fila": 2, "columna": 0})

    def test_rook_cost_sums_each_traversed_cell_but_not_origin(self) -> None:
        state = make_state(
            units=[{"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 1}],
            special_terrain={(3, 2): "camino", (3, 3): "bosque", (3, 4): "pantano", (3, 5): "camino"},
        )
        original = copy.deepcopy(state)

        self.assertEqual(move_cost(state, "R", {"fila": 3, "columna": 5}), 8)
        self.assertEqual(state, original)

    def test_knight_cost_is_only_the_destination_terrain(self) -> None:
        state = make_state(
            units=[{"id": "N", "bando": "A", "tipo": "knight", "fila": 1, "columna": 1}],
            walls={(1, 2)},
            special_terrain={(3, 2): "bosque"},
        )

        self.assertEqual(move_cost(state, "N", {"fila": 3, "columna": 2}), 4)
        self.assertEqual(terrain_cost(state, {"fila": 3, "columna": 2}), 4)
        self.assertEqual(compatibility_terrain_cost(state, 3, 2), 4)

    def test_bishop_cost_sums_diagonal_terrain(self) -> None:
        state = make_state(
            units=[{"id": "B", "bando": "A", "tipo": "bishop", "fila": 1, "columna": 1}],
            special_terrain={(2, 2): "bosque", (3, 3): "pantano"},
        )

        self.assertEqual(move_cost(state, "B", {"fila": 3, "columna": 3}), 6)

    def test_inactive_unit_does_not_block_a_ray_or_move(self) -> None:
        state = make_state(
            units=[
                {"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 1},
                {
                    "id": "inactive",
                    "bando": "A",
                    "tipo": "estandar",
                    "fila": 3,
                    "columna": 3,
                    "activo": False,
                },
            ]
        )

        moves = destinations(state, "R")
        self.assertIn((3, 3), moves)
        self.assertIn((3, 5), moves)
        self.assertEqual(legal_moves(state, "inactive"), [])

    def test_queen_blocks_sliding_piece_but_can_be_a_destination(self) -> None:
        state = make_state(
            units=[{"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 0}],
            queen=(3, 2),
        )

        moves = destinations(state, "R")
        self.assertIn((3, 2), moves)
        self.assertNotIn((3, 3), moves)

    def test_cannot_collect_queen_while_own_king_is_in_check(self) -> None:
        state = make_state(
            units=[
                {"id": "S", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0},
                {"id": "R", "bando": "B", "tipo": "rook", "fila": 3, "columna": 5},
            ],
            queen=(0, 1),
            kings={"A": [{"fila": 3, "columna": 0}], "B": []},
        )

        moves = destinations(state, "S")
        self.assertNotIn((0, 1), moves)
        self.assertIn((1, 0), moves)

    def test_discovered_check_after_moving_to_queen_is_rejected(self) -> None:
        state = make_state(
            units=[
                {"id": "A_ROOK", "bando": "A", "tipo": "rook", "fila": 3, "columna": 2},
                {"id": "B_ROOK", "bando": "B", "tipo": "rook", "fila": 3, "columna": 0},
            ],
            queen=(4, 2),
            kings={"A": [{"fila": 3, "columna": 6}], "B": []},
        )
        original = copy.deepcopy(state)

        self.assertFalse(is_in_check(state, "A"))
        self.assertTrue(is_in_check(state, "A", ("A_ROOK", (4, 2))))
        self.assertNotIn((4, 2), destinations(state, "A_ROOK"))
        self.assertEqual(state, original)

    def test_knight_bishop_and_standard_checks_prevent_queen_pickup(self) -> None:
        cases = (
            ("knight", (1, 2), (3, 3), (0, 0), (0, 1)),
            ("bishop", (0, 0), (3, 3), (0, 2), (0, 3)),
            ("estandar", (3, 2), (3, 3), (0, 0), (0, 1)),
        )
        for attacker_type, attacker, king, mover, queen in cases:
            with self.subTest(attacker=attacker_type):
                state = make_state(
                    units=[
                        {
                            "id": "A_UNIT",
                            "bando": "A",
                            "tipo": "estandar",
                            "fila": mover[0],
                            "columna": mover[1],
                        },
                        {
                            "id": "B_ATTACKER",
                            "bando": "B",
                            "tipo": attacker_type,
                            "fila": attacker[0],
                            "columna": attacker[1],
                        },
                    ],
                    queen=queen,
                    kings={"A": [{"fila": king[0], "columna": king[1]}], "B": []},
                )

                self.assertTrue(is_in_check(state, "A"))
                self.assertNotIn(queen, destinations(state, "A_UNIT"))

    def test_attacking_side_ally_blocks_check_and_allows_pickup(self) -> None:
        state = make_state(
            units=[
                {"id": "A_UNIT", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 0},
                {"id": "B_ROOK", "bando": "B", "tipo": "rook", "fila": 3, "columna": 0},
                {"id": "B_BLOCKER", "bando": "B", "tipo": "estandar", "fila": 3, "columna": 3},
            ],
            queen=(0, 1),
            kings={"A": [{"fila": 3, "columna": 6}], "B": []},
        )

        self.assertFalse(is_in_check(state, "A"))
        self.assertIn((0, 1), destinations(state, "A_UNIT"))

    def test_move_cost_rejects_wall_and_friendly_occupied_destinations(self) -> None:
        state = make_state(
            units=[
                {"id": "R", "bando": "A", "tipo": "rook", "fila": 3, "columna": 0},
                {"id": "ally", "bando": "A", "tipo": "estandar", "fila": 3, "columna": 1},
            ],
            walls={(3, 2)},
        )

        for destination in ((3, 1), (3, 2), (3, 3)):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                move_cost(state, "R", destination)

    def test_standard_move_cost_uses_destination_terrain(self) -> None:
        state = make_state(
            units=[{"id": "S", "bando": "A", "tipo": "estandar", "fila": 2, "columna": 2}],
            special_terrain={(2, 3): "pantano"},
        )

        self.assertEqual(move_cost(state, "S", {"fila": 2, "columna": 3}), 2)

    def test_unknown_and_inactive_units_have_no_moves(self) -> None:
        state = make_state(
            units=[
                {
                    "id": "inactive",
                    "bando": "A",
                    "tipo": "rook",
                    "fila": 3,
                    "columna": 3,
                    "activo": False,
                }
            ]
        )

        self.assertEqual(legal_moves(state, "inactive"), [])
        self.assertEqual(legal_moves(state, "missing"), [])

    def test_terrain_cost_rejects_blocked_and_out_of_bounds_cells(self) -> None:
        state = make_state(walls={(2, 2)})

        with self.assertRaises(ValueError):
            terrain_cost(state, {"fila": 2, "columna": 2})
        with self.assertRaises(ValueError):
            terrain_cost(state, {"fila": 7, "columna": 0})


if __name__ == "__main__":
    unittest.main()
