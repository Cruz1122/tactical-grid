from __future__ import annotations

from time import perf_counter
from typing import Any

from backend.algorithms.heuristics import _terrain_minima, second_heuristic
from backend.algorithms.search_common import (
    StateKey,
    prepare_search,
    search_result,
    unit_position,
    unit_successors,
)
from backend.game.engine import state_key, static_state_key


def beam_search(
    state: dict[str, Any], unit_id: str, goal: dict[str, Any], k: int = 2
) -> dict[str, Any]:
    """Busca por niveles y conserva como máximo k estados ordenados por h(n).

    `states_generated` cuenta claves de estado únicas vistas, incluso las descartadas;
    `max_frontier` mide solo estados conservados en el haz, nunca candidatos temporales.
    Beam Search no garantiza solución ni optimalidad de movimientos o costo.
    

    Purpose: Restringir a k candidatos por nivel de búsqueda heurística.
    Preconditions: k entero positivo; meta, ficha y estado válidos.
    Postconditions: Devuelve ruta encontrada o fallo sin completitud ni optimalidad garantizadas.
    Complexity: Tiempo O(D*k*b*log(k*b)) más generación; memoria O(k*b+Vvisitados).
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    started_at = perf_counter()  # Mide toda la llamada, incluida la validación y la reconstrucción.
    if type(k) is not int or k < 1:  # Rechaza anchos nulos, negativos y booleanos no enteros.
        result = search_result(
            None,
            {},
            {},
            {},
            unit_id,
            0,
            0,
            0,
            started_at,
            "El ancho del haz k debe ser un entero mayor que cero.",
        )
        result["candidates_discarded"] = 0
        return result

    target, error = prepare_search(state, unit_id, goal)  # Valida unidad, origen y objetivo antes de explorar.
    if target is None:  # Conserva el contrato común para entradas inválidas.
        result = search_result(None, {}, {}, {}, unit_id, 0, 0, 0, started_at, error)
        result["candidates_discarded"] = 0  # No hubo candidatos que el ancho pudiera descartar.
        return result

    static_key = static_state_key(state)  # Calcula una vez la parte fija compartida de las claves.
    root_key = state_key(state, static_key=static_key)  # Identifica el estado inicial completo.
    unit = next(item for item in state["unidades"] if item.get("id") == unit_id)  # Obtiene el tipo que define la heurística.
    unit_type = unit.get("tipo", "estandar")  # Mantiene fija la geometría de movimiento durante la búsqueda.
    minima = _terrain_minima(state)  # Precalcula los mínimos de terreno que reutiliza second_heuristic.
    beam = [root_key]  # El haz inicial contiene únicamente el estado de origen.
    states: dict[StateKey, dict[str, Any]] = {root_key: state}  # Guarda completos los estados seleccionados.
    parents: dict[StateKey, StateKey | None] = {root_key: None}  # Conserva padres solo para rutas retenidas.
    costs: dict[StateKey, float] = {root_key: 0.0}  # El costo real acumulado empieza en cero.
    selected_keys = {root_key}  # Evita ciclos reexpandiendo estados que ya formaron parte del haz.
    generated_keys = {root_key}  # Cuenta estados únicos sin impedir revisitar candidatos descartados.
    generated = 1  # El estado de origen cuenta como generado.
    expanded = 0  # Aún no se han expandido estados.
    max_frontier = 1  # La frontera es el tamaño del haz inicial, no sus candidatos.
    candidates_discarded = 0  # Acumula estados únicos por nivel que no caben en el haz.
    found_key: StateKey | None = None  # Se asigna al hallar una meta en un nivel conservado.
    sequence = 0  # Desempata de forma estable según el orden de sucesores del motor.

    while beam:  # Cada iteración procesa exactamente un nivel completo del árbol.
        for current_key in beam:  # Comprueba las metas del nivel antes de expandirlo.
            if unit_position(states[current_key], unit_id) == target:  # La posición de la unidad define el objetivo.
                found_key = current_key  # Guarda el estado que permite reconstruir el camino.
                break  # No expande otros estados al haber alcanzado ya el objetivo.
        if found_key is not None:  # Termina cuando una solución conservada llega al nivel actual.
            break  # No genera sucesores una vez encontrada la solución.

        candidates: dict[StateKey, tuple[float, float, int, dict[str, Any], StateKey]] = {}  # Agrupa sucesores únicos de todo el nivel.
        for current_key in beam:  # Expande cada estado retenido antes de seleccionar el siguiente haz.
            current_state = states[current_key]  # Recupera el estado necesario para aplicar las reglas reales.
            expanded += 1  # Cuenta cada estado del haz cuyos sucesores se generan.
            for next_state, step_cost in unit_successors(current_state, unit_id):  # Mueve solo la unidad pedida, sin alternar turnos.
                next_key = state_key(next_state, static_key=static_key)  # Distingue capturas, reapariciones y cambios de reina.
                if next_key in selected_keys:  # Un estado seleccionado anteriormente no se vuelve a expandir.
                    continue  # Evita ciclos sin cerrar permanentemente estados que fueron descartados.
                if next_key not in generated_keys:  # Cuenta una sola vez cada estado único generado en toda la búsqueda.
                    generated_keys.add(next_key)  # Registra la clave únicamente para las métricas.
                    generated += 1  # Cuenta el nuevo estado único aunque luego se descarte.

                next_cost = costs[current_key] + step_cost  # Acumula el costo real solo para informar y desempatar.
                next_position = unit_position(next_state, unit_id)  # Obtiene la posición usada por la heurística compartida.
                heuristic = second_heuristic(state, next_position, target, unit_type, minima)  # Ordena por h(n), nunca por g(n)+h(n).
                sequence += 1  # Da un orden reproducible a sucesores con heurística y costo iguales.
                previous = candidates.get(next_key)  # Comprueba si otro padre generó este mismo estado en el nivel.
                if previous is None or next_cost < previous[1]:  # Conserva la ruta de menor costo para una clave duplicada.
                    order = sequence if previous is None else previous[2]  # Mantiene el primer orden si el duplicado mejora su costo.
                    candidates[next_key] = (heuristic, next_cost, order, next_state, current_key)  # Deja una sola alternativa por estado.

        ordered_candidates = sorted(  # Selecciona por heurística y desempata por costo y orden estable.
            candidates.items(), key=lambda item: (item[1][0], item[1][1], item[1][2])
        )
        selected = ordered_candidates[:k]  # Limita el siguiente nivel a los mejores k estados distintos.
        candidates_discarded += len(ordered_candidates) - len(selected)  # Registra candidatos únicos excluidos por el ancho.
        beam = [key for key, _ in selected]  # El siguiente nivel contiene solo estados efectivamente conservados.
        for next_key, (_, next_cost, _, next_state, parent_key) in selected:  # Guarda datos solo de rutas retenidas.
            states[next_key] = next_state  # Permite expandir el estado en niveles posteriores.
            parents[next_key] = parent_key  # Enlaza el estado con el padre que produjo su ruta retenida.
            costs[next_key] = next_cost  # Conserva el costo acumulado real de esa ruta.
            selected_keys.add(next_key)  # Marca solo ahora como visitado el estado realmente seleccionado.
        max_frontier = max(max_frontier, len(beam))  # Mide el haz retenido, sin incluir candidatos temporales.

    result = search_result(  # Reutiliza reconstrucción y formato común para éxito, fallo y métricas.
        found_key, states, parents, costs, unit_id, generated, expanded, max_frontier, started_at
    )
    result["candidates_discarded"] = candidates_discarded  # Expone los descartes atribuibles al límite k.
    return result