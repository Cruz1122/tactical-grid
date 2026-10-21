from __future__ import annotations

from math import inf
from typing import Any

from backend.game.movement import terrain_cost

Position = tuple[int, int]
_UNIT_TYPES = {
    "knight": "knight",
    "caballo": "knight",
    "rook": "rook",
    "torre": "rook",
    "bishop": "bishop",
    "alfil": "bishop",
    "estandar": "estandar",
}


def manhattan(position: Position, goal: Position) -> int:
    """Calcula Manhattan, que no es admisible para todas las piezas o costos.

    Purpose: Calcular distancia ortogonal geométrica para orientar A*.
    Preconditions: Posición, objetivo y ficha de entrada válidos.
    Postconditions: Devuelve número no negativo; no se presume admisible para todas las piezas.
    Complexity: O(1) tiempo y espacio.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    return abs(position[0] - goal[0]) + abs(position[1] - goal[1])


def _terrain_minima(
    state: dict[str, Any],
) -> tuple[float, list[float], list[float]]:
    """Precalcula costos mínimos transitables globales, por fila y por columna."""
    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]
    row_minima = [inf] * rows
    column_minima = [inf] * columns
    min_cost = inf

    for row in range(rows):
        for column in range(columns):
            try:
                cost = terrain_cost(state, (row, column))
            except (TypeError, ValueError):
                continue
            if cost <= 0:
                continue
            row_minima[row] = min(row_minima[row], cost)
            column_minima[column] = min(column_minima[column], cost)
            min_cost = min(min_cost, cost)

    row_minima = [0.0 if value == inf else value for value in row_minima]
    column_minima = [0.0 if value == inf else value for value in column_minima]
    return (0.0 if min_cost == inf else min_cost), row_minima, column_minima


def second_heuristic(
    state: dict[str, Any],
    position: Position,
    goal: Position,
    unit_type: str,
    terrain_minima: tuple[float, list[float], list[float]] | None = None,
) -> float:
    """Estima el costo restante según geometría y mínimos de terreno.

    Purpose: Estimar una cota inferior del costo restante de acuerdo con la geometría de la pieza.
    Preconditions: Mapa válido y costos positivos procedentes del JSON.
    Postconditions: Devuelve estimación no negativa y nula en objetivo.
    Complexity: O(F*C) si calcula mínimos del mapa; O(1) con mínimos precalculados.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    min_cost, row_minima, column_minima = terrain_minima or _terrain_minima(state)
    dr = abs(position[0] - goal[0])
    dc = abs(position[1] - goal[1])
    kind = _UNIT_TYPES.get(unit_type, "estandar")

    if kind == "rook":
        return min_cost * (dr + dc)
    if kind == "bishop":
        return min_cost * max(dr, dc)
    if kind == "knight":
        return min_cost * max((dr + dc + 2) // 3, (max(dr, dc) + 1) // 2)

    row_step = 1 if goal[0] > position[0] else -1
    column_step = 1 if goal[1] > position[1] else -1
    rows_cost = sum(
        row_minima[row]
        for row in range(position[0] + row_step, goal[0] + row_step, row_step)
    )
    columns_cost = sum(
        column_minima[column]
        for column in range(position[1] + column_step, goal[1] + column_step, column_step)
    )
    return rows_cost + columns_cost