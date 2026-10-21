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


def alpha_beta(
    state: dict[str, Any], depth: int, action_order: str = "normal"
) -> dict[str, Any]:
    """Elige una acción con Minimax y poda alfa-beta sin alterar su utilidad.

    La raíz pasa alpha a cada respuesta y vuelve a buscar con ventana completa
    una cota empatada que podría ganar el desempate canónico. En los subárboles,
    alpha >= beta omite ramas; `nodes_pruned` cuenta esos sucesores inmediatos.
    """
    started_at = perf_counter()  # Mide desde antes de validar hasta construir la respuesta.
    validate_search(state, depth, action_order)  # Rechaza profundidad, turno y orden inválidos.
    max_side = state["turno"]  # El bando activo en la raíz es MAX para toda la búsqueda.
    metrics = {  # Inicializa los contadores usados también por Minimax.
        "depth_reached": 0,
        "nodes_generated": 0,
        "nodes_visited": 1,
        "nodes_evaluated": 0,
        "nodes_pruned": 0,
    }

    def search(
        node: dict[str, Any], remaining: int, alpha: float, beta: float, ply: int
    ) -> float:
        metrics["nodes_visited"] += 1  # Cuenta el nodo al comenzar su exploración.
        metrics["depth_reached"] = max(metrics["depth_reached"], ply)  # Registra la profundidad máxima realmente visitada.
        if check_winner(node) is not None or remaining == 0:  # Un final prevalece sobre la frontera de profundidad.
            metrics["nodes_evaluated"] += 1  # Cuenta la hoja que sí requiere función de evaluación.
            return evaluate(node, max_side)  # Usa exactamente la utilidad compartida con Minimax.

        pairs = ordered_successors(node, action_order)  # Obtiene acciones completas mediante el motor.
        metrics["nodes_generated"] += len(pairs)  # Cuenta todos los hijos legales materializados.
        if not pairs:  # Conserva un valor hoja ante estados sin sucesores.
            metrics["nodes_evaluated"] += 1  # Registra esta evaluación como hoja.
            return evaluate(node, max_side)  # Reutiliza la misma evaluación, sin inventar un paso.

        maximizing = node["turno"] == max_side  # Decide MAX/MIN según la alternancia real del motor.
        best_value = -inf if maximizing else inf  # MAX busca un límite alto y MIN uno bajo.
        for index, (_, next_state) in enumerate(pairs):  # Explora en el orden solicitado por el llamador.
            child_value = search(next_state, remaining - 1, alpha, beta, ply + 1)  # Evalúa el turno completo siguiente.
            if maximizing:  # En nodos MAX se conserva el mayor valor visto.
                best_value = max(best_value, child_value)  # Actualiza la mejor garantía de MAX.
                alpha = max(alpha, best_value)  # Eleva el límite inferior garantizado para MAX.
            else:  # En nodos MIN se conserva el menor valor visto.
                best_value = min(best_value, child_value)  # Actualiza la mejor respuesta de MIN.
                beta = min(beta, best_value)  # Reduce el límite superior permitido para MAX.
            if alpha >= beta:  # El intervalo cerrado ya no puede mejorar la decisión del antecesor.
                metrics["nodes_pruned"] += len(pairs) - index - 1  # Cuenta solo ramas hermanas aún no visitadas.
                break  # Omite esos sucesores sin evaluarlos como valores exactos.
        return best_value  # Devuelve el valor minimax o la cota suficiente para el antecesor.

    if check_winner(state) is not None or depth == 0:  # Detecta final de raíz antes del límite.
        metrics["nodes_evaluated"] += 1  # La raíz es la única hoja en este caso.
        value = evaluate(state, max_side)  # Devuelve evaluación terminal o estática sin acción.
        action = None  # No se recomienda una acción en profundidad cero ni tras finalizar.
    else:  # En una raíz activa con profundidad positiva hay que comparar sus acciones.
        pairs = ordered_successors(state, action_order)  # Genera todas las acciones legales del bando inicial.
        metrics["nodes_generated"] += len(pairs)  # Cuenta los hijos directos de la raíz.
        best_value = -inf  # La raíz siempre representa a MAX.
        action = None  # Aún no hay una recomendación seleccionada.
        best_key = None  # Conserva la clave para desempatar fuera del orden de exploración.
        for candidate_action, next_state in pairs:  # Explora las acciones raíz en el orden pedido.
            candidate_value = search(next_state, depth - 1, best_value, inf, 1)  # Alpha actual permite podar respuestas que no superan MAX.
            candidate_key = action_key(candidate_action)  # Usa el desempate canónico en todos los órdenes.
            if candidate_value == best_value and best_key is not None and candidate_key < best_key:  # Una cota igual solo importa si ganaría el desempate.
                candidate_value = search(next_state, depth - 1, -inf, inf, 1)  # Confirma el empate con un valor exacto.
            if candidate_value > best_value or (candidate_value == best_value and (best_key is None or candidate_key < best_key)):  # Compara valores exactos y desempata por clave.
                best_value = candidate_value  # Guarda el valor exacto de esta alternativa.
                action = candidate_action  # Guarda la acción legal original del motor.
                best_key = candidate_key  # Recuerda la clave elegida si aparece otro empate.
        if not pairs:  # El motor suele identificar esta condición como empate terminal.
            metrics["nodes_evaluated"] += 1  # Cuenta la raíz como hoja sin acciones.
            value = evaluate(state, max_side)  # Devuelve el valor real del estado sin fabricar una jugada.
        else:  # Toda raíz con acciones recibió al menos una evaluación exacta.
            value = best_value  # El máximo raíz es el resultado minimax de la búsqueda.

    return result_payload(  # Presenta la acción recomendada y métricas con formato compartido.
        "alpha_beta", action, value, depth, metrics, started_at, action_order
    )
