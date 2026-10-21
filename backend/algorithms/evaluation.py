from __future__ import annotations

from typing import Any

from backend.algorithms.adversarial_common import WIN_SCORE
from backend.game.engine import check_winner
from backend.game.movement import is_in_check, legal_moves

QUEEN_POSSESSION_SCORE = 1_000
BASE_PROXIMITY_SCORE = 200
QUEEN_PROXIMITY_SCORE = 100
ACTIVE_UNIT_SCORE = 60
CHECK_SCORE = 80
SAFE_CARRIER_SCORE = 150
THREATENED_CARRIER_SCORE = -150


def _position(value: Any) -> tuple[int, int] | None:
    """Lee coordenadas del JSON del juego sin asumir una posición fija."""
    if not isinstance(value, dict):
        return None
    row = value.get("fila", value.get("row"))
    column = value.get("columna", value.get("column"))
    if type(row) is not int or type(column) is not int:
        return None
    return row, column


def _largest_map_distance(state: dict[str, Any]) -> int:
    """Obtiene la mayor distancia Manhattan posible según el tamaño del mapa."""
    board = state.get("mapa")
    if not isinstance(board, dict):
        return 0
    rows = board.get("filas", 0)
    columns = board.get("columnas", 0)
    if type(rows) is not int or type(columns) is not int:
        return 0
    return max(rows - 1, 0) + max(columns - 1, 0)


def _proximity_score(
    position: tuple[int, int], target: tuple[int, int], state: dict[str, Any], maximum: float
) -> float:
    """Normaliza Manhattan por el mayor recorrido posible del mapa."""
    largest_distance = _largest_map_distance(state)
    distance = abs(position[0] - target[0]) + abs(position[1] - target[1])
    if largest_distance == 0:
        return maximum if distance == 0 else 0.0
    normalized_distance = max(0.0, 1.0 - distance / largest_distance)
    return maximum * normalized_distance


def _carrier_threatened(
    state: dict[str, Any], carrier: dict[str, Any]
) -> bool:
    """Comprueba si una pieza enemiga puede capturar legalmente en su próximo turno."""
    carrier_position = _position(carrier)
    if carrier_position is None:
        return False
    enemy_side = "B" if carrier.get("bando") == "A" else "A"
    for unit in state.get("unidades", []):
        if (
            unit.get("activo", True) is not True
            or unit.get("bando") != enemy_side
            or not isinstance(unit.get("id"), str)
        ):
            continue
        if carrier_position in {
            _position(destination) for destination in legal_moves(state, unit["id"])
        }:
            return True
    return False


def _side_score(state: dict[str, Any], side: str) -> float:
    """Suma factores estratégicos independientes para un bando."""
    units = [
        unit
        for unit in state.get("unidades", [])
        if unit.get("activo", True) is True and unit.get("bando") == side
    ]
    score = ACTIVE_UNIT_SCORE * len(units)
    game = state.get("juego", {})
    carrier_id = game.get("portador_recurso") if isinstance(game, dict) else None
    carrier = next(
        (unit for unit in state.get("unidades", []) if unit.get("id") == carrier_id),
        None,
    )

    if carrier is not None and carrier.get("bando") == side:
        score += QUEEN_POSSESSION_SCORE
        carrier_position = _position(carrier)
        base = _position(state.get("bases", {}).get(side))
        if carrier_position is not None and base is not None:
            score += _proximity_score(carrier_position, base, state, BASE_PROXIMITY_SCORE)
        if _carrier_threatened(state, carrier):
            score += THREATENED_CARRIER_SCORE
        else:
            score += SAFE_CARRIER_SCORE

    queen_position = _position(state.get("recurso")) if carrier_id is None else None
    if queen_position is not None:
        unit_positions: list[tuple[int, int]] = []
        for unit in units:
            position = _position(unit)
            if position is not None:
                unit_positions.append(position)
        if unit_positions:
            nearest_unit = min(
                unit_positions,
                key=lambda position: abs(position[0] - queen_position[0])
                + abs(position[1] - queen_position[1]),
            )
            score += _proximity_score(
                nearest_unit, queen_position, state, QUEEN_PROXIMITY_SCORE
            )
        opponent = "B" if side == "A" else "A"
        if is_in_check(state, opponent):
            score += CHECK_SCORE

    return score


def evaluate(state: dict[str, Any], side: str) -> float:
    """Evalúa un estado completo desde el punto de vista de A o B.

    Los resultados terminales prevalecen sobre cualquier factor posicional. En los
    demás estados se calculan las puntuaciones de ambos bandos por separado para
    conservar simetría y el mismo valor absoluto independientemente del llamador.
    """
    if side not in ("A", "B"):
        raise ValueError("El bando de evaluación debe ser 'A' o 'B'")
    winner = check_winner(state)
    if winner is not None:
        if winner == "empate":
            return 0.0
        return float(WIN_SCORE if winner == side else -WIN_SCORE)

    opponent = "B" if side == "A" else "A"
    return _side_score(state, side) - _side_score(state, opponent)
