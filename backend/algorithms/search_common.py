from __future__ import annotations

from time import perf_counter
from typing import Any

from backend.game.engine import hypothetical_move
from backend.game.movement import legal_moves, move_cost, terrain_cost

Position = tuple[int, int]
StateKey = tuple[Any, ...]


def prepare_search(
    state: dict[str, Any], unit_id: str, goal: dict[str, Any]
) -> tuple[Position | None, str | None]:
    """Validar petición de navegación de unidad y meta sin modificar la partida.
    
    Purpose: Validar petición de navegación de unidad y meta sin modificar la partida.
    Preconditions: Estado preparado y parámetros con estructura correcta.
    Postconditions: Meta normalizada o error explícito para dato inválido.
    Complexity: Validación y búsqueda de unidad O(U), más validaciones de posición.
    AI usage: Yes.
    AI intervention: IA asistió el diseño del contrato común entre cinco búsquedas.
    Student validation: Suite de navegación aprobada; revisión individual pendiente.
    """
    if isinstance(goal, dict):
        row = goal.get("fila", goal.get("row"))
        column = goal.get("columna", goal.get("column"))
    elif isinstance(goal, (tuple, list)) and len(goal) == 2:
        row, column = goal
    else:
        return None, "El objetivo debe incluir fila y columna."
    if type(row) is not int or type(column) is not int:
        return None, "Las coordenadas del objetivo deben ser enteros."
    if not isinstance(unit_id, str) or not unit_id.strip():
        return None, "El identificador de unidad no es válido."

    units = state.get("unidades")
    if not isinstance(units, list):
        return None, "El estado no contiene una lista válida de unidades."
    unit = next(
        (item for item in units if isinstance(item, dict) and item.get("id") == unit_id),
        None,
    )
    if unit is None:
        return None, f"No existe la unidad {unit_id!r}."
    if unit.get("activo", True) is not True:
        return None, f"La unidad {unit_id!r} está inactiva."
    start_row, start_column = unit.get("fila"), unit.get("columna")
    if type(start_row) is not int or type(start_column) is not int:
        return None, f"La unidad {unit_id!r} tiene coordenadas inválidas."

    start = (start_row, start_column)
    target = (row, column)
    try:
        terrain_cost(state, start)
    except (TypeError, ValueError) as error:
        return None, f"El origen de {unit_id!r} no es transitable: {error}"
    try:
        terrain_cost(state, target)
    except (TypeError, ValueError) as error:
        return None, f"El objetivo no es transitable: {error}"
    return target, None


def unit_position(state: dict[str, Any], unit_id: str) -> Position:
    """Obtiene la posición actual de la unidad que se está navegando."""
    unit = next(item for item in state["unidades"] if item.get("id") == unit_id)
    return unit["fila"], unit["columna"]


def unit_successors(
    state: dict[str, Any], unit_id: str
) -> list[tuple[dict[str, Any], float]]:
    """Producir estados hipotéticos y costos de una sola unidad conservando efectos del motor.
    
    Purpose: Producir estados hipotéticos y costos de una sola unidad conservando efectos del motor.
    Preconditions: Unidad válida y estado navegable.
    Postconditions: Sucesores legales con costos reales; no alterna enemigos ni muta el oficial.
    Complexity: O(b*(T_move+S)), con b destinos, T_move reglas y S copia/validación de estado.
    AI usage: Yes.
    AI intervention: IA participó en separación de navegación vs. transición adversarial y diseño de sucesores.
    Student validation: Regresiones de capturas y verificación de rutas; revisión humana pendiente.
    """
    successors = []
    for destination in legal_moves(state, unit_id):
        cost = move_cost(state, unit_id, destination)
        next_state = hypothetical_move(state, unit_id, destination)
        successors.append((next_state, cost))
    return successors


def search_result(
    found_key: StateKey | None,
    states: dict[StateKey, dict[str, Any]],
    parents: dict[StateKey, StateKey | None],
    costs: dict[StateKey, float],
    unit_id: str,
    generated: int,
    expanded: int,
    max_frontier: int,
    started_at: float,
    error: str | None = None,
) -> dict[str, Any]:
    """Reconstruir ruta por padres y empaquetar métricas comunes de búsquedas.
    
    Purpose: Reconstruir ruta por padres y empaquetar métricas comunes de búsquedas.
    Preconditions: Diccionarios de padres/estados/costos coherentes; reloj iniciado.
    Postconditions: Resultado uniforme para éxito, fallo y error de entrada.
    Complexity: O(L) para reconstruir ruta de L estados, más serialización del resultado.
    AI usage: Yes.
    AI intervention: IA contribuyó al formato compartido y a registrar tiempo/estados.
    Student validation: Resultados usados en comparaciones de casos 1–5; revisión individual pendiente.
    """
    path: list[dict[str, int]] = []
    total_cost: float | None = None
    moves: int | None = None
    if found_key is not None:
        cursor: StateKey | None = found_key
        while cursor is not None:
            row, column = unit_position(states[cursor], unit_id)
            path.append({"fila": row, "columna": column})
            cursor = parents[cursor]
        path.reverse()
        moves = len(path) - 1
        total_cost = costs[found_key]

    return {
        "found": found_key is not None,
        "input_valid": error is None,
        "error": error,
        "path": path,
        "moves": moves,
        "cost": total_cost,
        "states_generated": generated,
        "states_expanded": expanded,
        "max_frontier": max_frontier,
        "elapsed_seconds": perf_counter() - started_at,
    }