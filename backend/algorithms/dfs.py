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


def dfs(state: dict[str, Any], unit_id: str, goal: dict[str, Any]) -> dict[str, Any]:
    """Recorrer la navegación de una unidad mediante pila LIFO y visitados.
    
    Purpose: Recorrer la navegación de una unidad mediante pila LIFO y visitados.
    Preconditions: Escenario válido, unidad seleccionada y meta; mismo generador que BFS.
    Postconditions: Ruta legal si existe y se alcanza en el recorrido; no garantiza mínimo costo ni movimientos.
    Complexity: O(V+E) sobre grafo alcanzable finito, más sucesores; O(V) memoria.
    AI usage: Yes.
    AI intervention: Asistencia de IA en generación de búsqueda iterativa, orden de sucesores y registro de métricas.
    Student validation: Caso 1 comparado con BFS; suite automatizada aprobada. Revisión individual pendiente.
    """
    started_at = perf_counter()  # Inicia la medición antes de preparar la búsqueda.
    target, error = prepare_search(state, unit_id, goal)  # Valida los datos antes de explorar.
    if target is None:  # Distingue una entrada inválida de una meta inalcanzable.
        return search_result(None, {}, {}, {}, unit_id, 0, 0, 0, started_at, error)  # Devuelve el motivo sin lanzar por falta de ruta.

    static_key = static_state_key(state)  # Congela una vez el mapa compartido por todos los nodos.
    root_key = state_key(state, static_key=static_key)  # Combina el escenario con el estado dinámico.
    frontier = [root_key]  # La lista actuará como pila: el último estado añadido será el próximo.
    states: dict[StateKey, dict[str, Any]] = {root_key: state}  # Guarda cada estado completo.
    parents: dict[StateKey, StateKey | None] = {root_key: None}  # El origen no tiene predecesor.
    costs: dict[StateKey, float] = {root_key: 0.0}  # El origen no ha consumido costo de movimiento.
    generated = 1  # Cuenta el estado inicial como generado.
    expanded = 0  # Aún no se han generado sucesores de ningún estado.
    max_frontier = 1  # La frontera comienza con únicamente el origen.
    found_key: StateKey | None = None  # Se mantiene vacío hasta extraer la meta de la pila.

    while frontier:  # Continúa mientras haya estados pendientes de explorar.
        current_key = frontier.pop()  # LIFO profundiza por la rama añadida más recientemente.
        current_state = states[current_key]  # Recupera el estado completo para aplicar reglas.
        if unit_position(current_state, unit_id) == target:  # La meta se prueba al extraer el nodo.
            found_key = current_key  # Guarda la clave para reconstruir la ruta final.
            break  # DFS se detiene en la primera meta, sin garantizar que sea la más corta.

        expanded += 1  # Este nodo no era meta y sus sucesores se van a explorar.
        next_states = unit_successors(current_state, unit_id)  # Obtiene sucesores en orden del motor.
        for next_state, step_cost in reversed(next_states):  # Invierte inserción para explorar el primero antes.
            next_key = state_key(next_state, static_key=static_key)  # Reutiliza el mapa y distingue capturas/reapariciones.
            if next_key in parents:  # Un estado ya descubierto no debe entrar otra vez en la pila.
                continue  # Evita ciclos y conserva el primer predecesor determinista.
            states[next_key] = next_state  # Guarda el estado necesario para expandirlo después.
            parents[next_key] = current_key  # Registra el predecesor para reconstruir el camino.
            costs[next_key] = costs[current_key] + step_cost  # Acumula el costo real del movimiento.
            frontier.append(next_key)  # LIFO pondrá este estado encima de la pila.
            generated += 1  # Cuenta solamente estados nuevos descubiertos.
        max_frontier = max(max_frontier, len(frontier))  # Registra la frontera más grande observada.

    return search_result(  # Comparte el formato de salida y reconstrucción con BFS.
        found_key, states, parents, costs, unit_id, generated, expanded, max_frontier, started_at  # Entrega ruta, costos y métricas acumuladas.
    )