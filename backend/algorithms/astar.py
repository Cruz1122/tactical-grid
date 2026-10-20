from __future__ import annotations

import heapq
from itertools import count
from math import inf
from time import perf_counter
from typing import Any

from backend.algorithms.search_common import (
    StateKey,
    prepare_search,
    search_result,
    unit_position,
    unit_successors,
)
from backend.game.engine import state_key, static_state_key
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
    """Devuelve la distancia Manhattan clásica, sin ajustes por tipo de unidad."""
    # Esta referencia puede sobreestimar para caballo, torre y alfil, y con costos inferiores a uno.
    return abs(position[0] - goal[0]) + abs(position[1] - goal[1])


def _terrain_minima(
    state: dict[str, Any],
) -> tuple[float, list[float], list[float]]:
    """Precalcula el menor costo transitable global, por fila y por columna."""
    # Lee las dimensiones una vez para dimensionar los mínimos del mapa.
    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]
    # Inf permite reemplazar cada mínimo al encontrar terreno transitable.
    row_minima = [inf] * rows
    column_minima = [inf] * columns
    min_cost = inf
    # Recorre cada casilla para considerar solo terrenos transitables.
    for row in range(rows):
        for column in range(columns):
            try:
                cost = terrain_cost(state, (row, column))
            except (TypeError, ValueError):
                # Obstáculos y casillas mal definidas no aportan costos a la cota.
                continue
            if cost <= 0:
                # Excluye costos no positivos para mantener las cotas conservadoras.
                continue
            row_minima[row] = min(row_minima[row], cost)
            column_minima[column] = min(column_minima[column], cost)
            min_cost = min(min_cost, cost)
    # Una fila o columna sin paso transitable aporta cero para no sobreestimar.
    row_minima = [0.0 if value == inf else value for value in row_minima]
    column_minima = [0.0 if value == inf else value for value in column_minima]
    # Si el mapa no tiene costos positivos, cero es la cota conservadora.
    return (0.0 if min_cost == inf else min_cost), row_minima, column_minima


def second_heuristic(
    state: dict[str, Any],
    position: Position,
    goal: Position,
    unit_type: str,
    terrain_minima: tuple[float, list[float], list[float]] | None = None,
) -> float:
    """Estima el costo restante según la geometría y el tipo de unidad."""
    # Reutiliza los mínimos precalculados por A* o los calcula para una llamada aislada.
    min_cost, row_minima, column_minima = terrain_minima or _terrain_minima(state)
    # Las distancias absolutas evitan depender de la dirección del desplazamiento.
    dr = abs(position[0] - goal[0])
    dc = abs(position[1] - goal[1])
    # Canoniza los nombres alternativos para aplicar la geometría del motor.
    kind = _UNIT_TYPES.get(unit_type, "estandar")
    if kind == "rook":
        # La torre recorre cada casilla, así que hacen falta al menos dr + dc pasos de terreno.
        return min_cost * (dr + dc)
    if kind == "bishop":
        # Cada paso diagonal cambia como máximo una fila y una columna.
        return min_cost * max(dr, dc)
    if kind == "knight":
        # Cada salto cambia Manhattan como máximo tres y un eje como máximo dos.
        return min_cost * max((dr + dc + 2) // 3, (max(dr, dc) + 1) // 2)

    # Los movimientos estándar son ortogonales: cada fila y columna nueva exige otro paso.
    row_step = 1 if goal[0] > position[0] else -1
    column_step = 1 if goal[1] > position[1] else -1
    # Omite la fila inicial y suma mínimos de todas las filas alcanzadas hasta la meta.
    rows_cost = sum(
        row_minima[row]
        for row in range(position[0] + row_step, goal[0] + row_step, row_step)
    )
    # Omite la columna inicial y suma mínimos de todas las columnas alcanzadas hasta la meta.
    columns_cost = sum(
        column_minima[column]
        for column in range(position[1] + column_step, goal[1] + column_step, column_step)
    )
    # Las entradas de fila y columna son movimientos distintos para una unidad ortogonal.
    return rows_cost + columns_cost


def astar(
    state: dict[str, Any],
    unit_id: str,
    goal: dict[str, Any],
    heuristic: str = "manhattan",
) -> dict[str, Any]:
    """Busca una ruta con prioridad f(n) = g(n) + h(n), sin mutar el estado."""
    # Inicia el cronómetro antes de validar para incluir toda la búsqueda.
    started_at = perf_counter()
    # Valida el origen, la unidad y la casilla objetivo usando el contrato común.
    target, error = prepare_search(state, unit_id, goal)
    if target is None:
        # Devuelve los errores de entrada con el mismo formato que BFS y DFS.
        return search_result(None, {}, {}, {}, unit_id, 0, 0, 0, started_at, error)
    if heuristic not in ("manhattan", "second"):
        # Rechaza nombres desconocidos para que no se ejecute una búsqueda ambigua.
        return search_result(
            None,
            {},
            {},
            {},
            unit_id,
            0,
            0,
            0,
            started_at,
            "La heurística debe ser 'manhattan' o 'second'.",
        )

    # Comparte la parte estática del escenario al crear claves de estados.
    static_key = static_state_key(state)
    # Guarda el estado de origen como primer nodo descubierto.
    root_key = state_key(state, static_key=static_key)
    # Recupera el tipo fijo de la unidad seleccionada para elegir la heurística.
    unit = next(item for item in state["unidades"] if item.get("id") == unit_id)
    unit_type = unit.get("tipo", "estandar")
    # Precalcula una sola vez los mínimos usados por la heurística propia.
    minima = _terrain_minima(state) if heuristic == "second" else None

    # Reserva una secuencia estable para desempatar sin comparar estados complejos.
    tie_breaker = count()
    # Inserta el origen con g=0 y prioridad f=g+h.
    root_position = unit_position(state, unit_id)
    root_h = (
        manhattan(root_position, target)
        if heuristic == "manhattan"
        else second_heuristic(state, root_position, target, unit_type, minima)
    )
    frontier: list[tuple[float, int, float, StateKey]] = []
    heapq.heappush(frontier, (root_h, next(tie_breaker), 0.0, root_key))
    # Conserva estados completos para generar sucesores y reconstruir la ruta.
    states: dict[StateKey, dict[str, Any]] = {root_key: state}
    # Guarda el mejor predecesor conocido para cada clave de estado.
    parents: dict[StateKey, StateKey | None] = {root_key: None}
    # g_score contiene el menor costo real conocido para cada estado.
    costs: dict[StateKey, float] = {root_key: 0.0}
    generated = 1
    expanded = 0
    max_frontier = 1
    found_key: StateKey | None = None

    # Sigue mientras haya candidatos pendientes en la frontera priorizada.
    while frontier:
        _, _, current_g, current_key = heapq.heappop(frontier)
        # Descarta entradas antiguas que quedaron en el heap tras una mejora de g.
        if current_g != costs[current_key]:
            continue
        current_state = states[current_key]
        # Acepta la meta al extraerla con su mejor prioridad conocida.
        if unit_position(current_state, unit_id) == target:
            found_key = current_key
            break

        # Cuenta solo extracciones vigentes que realmente expanden movimientos.
        expanded += 1
        # Genera movimientos legales hipotéticos solo para la unidad seleccionada.
        for next_state, step_cost in unit_successors(current_state, unit_id):
            # La clave incluye capturas, portador y demás cambios dinámicos del motor.
            next_key = state_key(next_state, static_key=static_key)
            # Suma el costo real del movimiento para obtener el nuevo g.
            next_g = current_g + step_cost
            # Ignora rutas iguales o más caras, pero permite mejorar y reabrir estados.
            if next_g >= costs.get(next_key, inf):
                continue
            # Cuenta una clave solo al descubrirla por primera vez, como BFS y DFS.
            if next_key not in costs:
                generated += 1
            # Actualiza el mejor costo, estado y padre cuando aparece una ruta mejor.
            costs[next_key] = next_g
            states[next_key] = next_state
            parents[next_key] = current_key
            # Evalúa h desde la posición concreta de este sucesor.
            next_position = unit_position(next_state, unit_id)
            next_h = (
                manhattan(next_position, target)
                if heuristic == "manhattan"
                else second_heuristic(state, next_position, target, unit_type, minima)
            )
            # Encola f=g+h y usa secuencia de inserción como desempate determinista.
            heapq.heappush(
                frontier, (next_g + next_h, next(tie_breaker), next_g, next_key)
            )
        # Registra el mayor heap observado, incluyendo entradas obsoletas pendientes.
        max_frontier = max(max_frontier, len(frontier))

    # Reconstruye la ruta y devuelve métricas con el formato compartido.
    return search_result(
        found_key,
        states,
        parents,
        costs,
        unit_id,
        generated,
        expanded,
        max_frontier,
        started_at,
    )
