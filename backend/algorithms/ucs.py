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


def ucs(state: dict[str, Any], unit_id: str, goal: dict[str, Any]) -> dict[str, Any]:
    """Busca costo mínimo sin modificar el estado recibido.

    `states_generated` cuenta claves únicas (incluido el origen); `states_expanded`
    cuenta extracciones vigentes que no son meta; `max_frontier` incluye entradas
    obsoletas. El tiempo incluye validación y reconstrucción del camino.
    

    Purpose: Encontrar la ruta de menor costo con una cola de prioridad.
    Preconditions: Costos de transición positivos y entrada válida.
    Postconditions: Devuelve una ruta de costo mínimo o fallo explícito sin mutar el estado.
    Complexity: Tiempo O((V+E) log V) más generación; espacio O(V+E), en modelo de grafo explícito.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    started_at = perf_counter()  # Mide desde la validación hasta la reconstrucción del camino.
    target, error = prepare_search(state, unit_id, goal)  # Valida unidad, origen y destino antes de explorar.
    if target is None:  # Separa los datos inválidos de una búsqueda válida sin ruta.
        return search_result(None, {}, {}, {}, unit_id, 0, 0, 0, started_at, error)  # Devuelve el error con el contrato compartido.

    static_key = static_state_key(state)  # Congela una sola vez el escenario estático para todas las claves.
    root_key = state_key(state, static_key=static_key)  # Identifica el estado inicial, incluidos sus datos dinámicos.
    tie_breaker = count()  # Desempata con orden de inserción sin comparar claves complejas.
    frontier = [(0.0, next(tie_breaker), root_key)]  # UCS prioriza únicamente el costo real acumulado g(n).
    states: dict[StateKey, dict[str, Any]] = {root_key: state}  # Conserva estados completos para sucesores y camino.
    parents: dict[StateKey, StateKey | None] = {root_key: None}  # El origen no tiene estado padre.
    costs: dict[StateKey, float] = {root_key: 0.0}  # Inicializa g(origen) en cero.
    generated = 1  # Cuenta el estado inicial como generado.
    expanded = 0  # Aún no se ha extraído ningún estado no objetivo para expandirlo.
    max_frontier = 1  # La frontera inicial contiene solo el origen.
    found_key: StateKey | None = None  # Se asigna únicamente al extraer la meta con costo óptimo.

    while frontier:  # Continúa hasta hallar la meta o agotar la frontera.
        current_g, _, current_key = heapq.heappop(frontier)  # Extrae el candidato de menor costo acumulado.
        if current_g != costs[current_key]:  # Las mejoras dejan entradas antiguas que ya no representan el mejor g.
            continue  # Ignora esa entrada obsoleta sin expandirla.
        current_state = states[current_key]  # Recupera la versión del estado que tiene el costo extraído.
        if unit_position(current_state, unit_id) == target:  # La meta se acepta al extraerla, no al generarla.
            found_key = current_key  # Conserva la clave para reconstruir el camino óptimo.
            break  # Con costos de transición positivos, este g es el costo mínimo de la meta.

        expanded += 1  # Cuenta solo estados vigentes extraídos que sí generan sucesores.
        for next_state, step_cost in unit_successors(current_state, unit_id):  # Mueve solo la unidad seleccionada con reglas reales.
            next_key = state_key(next_state, static_key=static_key)  # Distingue capturas, reapariciones y cambios del recurso.
            next_g = current_g + step_cost  # Suma el costo real de esta transición al costo acumulado.
            if next_g >= costs.get(next_key, inf):  # Descarta rutas iguales o peores y conserva cualquier mejora estricta.
                continue  # Evita ciclos de costo positivo y estados redundantes.
            if next_key not in costs:  # Solo un estado nunca visto incrementa la métrica de generados.
                generated += 1  # Cuenta cada clave única una sola vez, aunque luego mejore su costo.
            costs[next_key] = next_g  # Registra el mejor costo conocido para el sucesor.
            states[next_key] = next_state  # Guarda el estado correspondiente a esa ruta mejorada.
            parents[next_key] = current_key  # Actualiza su padre para reconstruir la ruta de menor costo.
            heapq.heappush(frontier, (next_g, next(tie_breaker), next_key))  # Encola la mejora con desempate determinista.
        max_frontier = max(max_frontier, len(frontier))  # Incluye entradas obsoletas pendientes, igual que A*.

    return search_result(  # Comparte reconstrucción, formato y métricas con BFS, DFS y A*.
        found_key, states, parents, costs, unit_id, generated, expanded, max_frontier, started_at  # Devuelve resultado y mediciones de UCS.
    )