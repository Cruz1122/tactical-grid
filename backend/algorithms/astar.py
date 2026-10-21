from __future__ import annotations

import heapq
from itertools import count
from math import inf
from time import perf_counter
from typing import Any

from backend.algorithms.heuristics import _terrain_minima, manhattan, second_heuristic
from backend.algorithms.search_common import (
    StateKey,
    prepare_search,
    search_result,
    unit_position,
    unit_successors,
)
from backend.game.engine import state_key, static_state_key


def astar(
    state: dict[str, Any],
    unit_id: str,
    goal: dict[str, Any],
    heuristic: str = "manhattan",
) -> dict[str, Any]:
    """Buscar rutas con prioridad f=g+h, admitiendo Manhattan o heurística propia.
    
    Purpose: Buscar rutas con prioridad f=g+h, admitiendo Manhattan o heurística propia.
    Preconditions: Costos positivos; meta y unidad válidas; selector de heurística soportado.
    Postconditions: Devuelve ruta encontrada y métricas; optimalidad garantizable solo con heurística apropiada.
    Complexity: O((V+E) log V) bajo condiciones de grafo explícito, más costo de h y de generar sucesores; memoria proporcional a frontera y registros.
    AI usage: Yes.
    AI intervention: IA participó en diseño e implementación de heap, reaperturas, integración de h y pruebas comparativas.
    Student validation: Caso 4: ambas rutas de costo 32, propia expandió 197 vs. 257 de Manhattan; validación humana pendiente.
    """
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