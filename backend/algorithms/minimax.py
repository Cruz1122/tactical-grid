from __future__ import annotations

from math import inf
from time import perf_counter
from typing import Any

from backend.algorithms.adversarial_common import (
    action_key,
    ordered_successors,
    result_payload,
    validate_search,
)
from backend.algorithms.evaluation import evaluate
from backend.game.engine import check_winner


def minimax(
    state: dict[str, Any], depth: int, action_order: str = "normal"
) -> dict[str, Any]:
    """Elige una acción con Minimax y devuelve la decisión y sus métricas.

    Una profundidad es una acción completa; la raíz cuenta como profundidad cero.
    `nodes_pruned` vale cero: Minimax visita todos los sucesores legales.
    """
    started_at = perf_counter()  # Inicia el cronómetro antes de validar y buscar.
    validate_search(state, depth, action_order)  # Rechaza profundidad, turno u orden inválidos.
    max_side = state["turno"]  # El bando que tiene el turno en la raíz siempre es MAX.
    metrics = {  # Inicializa contadores con definiciones compartidas por alfa-beta.
        "depth_reached": 0,
        "nodes_generated": 0,
        "nodes_visited": 0,
        "nodes_evaluated": 0,
        "nodes_pruned": 0,
    }

    def search(
        node: dict[str, Any], remaining: int, ply: int
    ) -> tuple[float, dict[str, Any] | None]:
        metrics["nodes_visited"] += 1  # Cuenta cada nodo al entrar a la búsqueda.
        metrics["depth_reached"] = max(metrics["depth_reached"], ply)  # Conserva el nivel más profundo alcanzado.
        if check_winner(node) is not None or remaining == 0:  # Resuelve terminales antes de aplicar el límite.
            metrics["nodes_evaluated"] += 1  # Cuenta una hoja terminal o de profundidad.
            return evaluate(node, max_side), None  # Evalúa siempre desde la perspectiva de MAX.

        pairs = ordered_successors(node, action_order)  # Reutiliza acciones y transiciones del motor.
        metrics["nodes_generated"] += len(pairs)  # Cuenta todos los sucesores legales materializados.
        if not pairs:  # La generación vacía también se trata como hoja defensiva.
            metrics["nodes_evaluated"] += 1  # Registra la hoja para mantener métricas completas.
            return evaluate(node, max_side), None  # El motor normalmente habrá detectado empate arriba.

        maximizing = node["turno"] == max_side  # El tipo de nodo deriva del turno real, no de la profundidad.
        best_value = -inf if maximizing else inf  # MAX parte de menos infinito y MIN de más infinito.
        best_action = None  # Aún no se ha elegido una acción de este nodo.
        best_key = None  # Guarda la clave canónica para resolver empates sin depender del orden.
        for action, next_state in pairs:  # Considera todas las acciones legales del bando activo.
            child_value, _ = search(next_state, remaining - 1, ply + 1)  # Simula la acción y alterna por el estado resultante.
            candidate_key = action_key(action)  # Calcula un desempate estable para esta acción.
            better_value = child_value > best_value if maximizing else child_value < best_value  # MAX maximiza y MIN minimiza.
            tied_better_action = child_value == best_value and (best_key is None or candidate_key < best_key)  # El desempate es canónico.
            if better_value or tied_better_action:  # Actualiza por valor o por el desempate fijo.
                best_value = child_value  # Conserva el valor minimax de la mejor opción vista.
                best_action = action  # Conserva la acción real, no una coordenada inferida.
                best_key = candidate_key  # Recuerda la clave seleccionada para empates posteriores.
        return best_value, best_action  # Devuelve el mejor valor y la acción de este nodo.

    value, action = search(state, depth, 0)  # Comienza con el estado oficial sin mutarlo.
    return result_payload(  # Devuelve el formato de decisión y contadores comparables.
        "minimax", action, value, depth, metrics, started_at, action_order
    )
