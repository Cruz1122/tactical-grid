from __future__ import annotations

from time import perf_counter
from typing import Any

from backend.game.engine import action_successors

WIN_SCORE = 100_000
ACTION_ORDERS = ("normal", "reverse")


def validate_search(state: dict[str, Any], depth: int, action_order: str) -> None:
    """Validar parámetros de profundidad, orden y bando para decisión adversarial.
    
    Purpose: Validar parámetros de profundidad, orden y bando para decisión adversarial.
    Preconditions: Estado preparado; parámetros sin coacción de tipos.
    Postconditions: Rechaza valores inválidos sin tocar la partida.
    Complexity: O(1).
    AI usage: Yes.
    AI intervention: IA asistió el diseño de contrato de entrada de Minimax y alfa-beta.
    Student validation: Suite de parámetros adversariales; validación humana pendiente.
    """
    if type(depth) is not int or depth < 0:
        raise ValueError("La profundidad debe ser un entero mayor o igual que cero")
    if action_order not in ACTION_ORDERS:
        raise ValueError("El orden de acciones debe ser 'normal' o 'reverse'")
    if state.get("turno") not in ("A", "B"):
        raise ValueError("El estado debe indicar el turno 'A' o 'B'")


def action_key(action: dict[str, Any]) -> tuple[int, str, int, int]:
    """Generar orden canónico independiente del recorrido normal/inverso.
    
    Purpose: Generar orden canónico independiente del recorrido normal/inverso.
    Preconditions: Acción legal de mover o recoger.
    Postconditions: Tupla comparable para desempates deterministas.
    Complexity: O(1) sobre coordenadas/ID.
    AI usage: Yes.
    AI intervention: IA asistió la estrategia de desempate común de ambos algoritmos.
    Student validation: Comparaciones de órdenes normal/reverse; validación humana pendiente.
    """
    if action.get("type") == "collect":
        return (1, str(action.get("unit_id", "")), -1, -1)
    destination = action.get("destination", {})
    return (
        0,
        str(action.get("unit_id", "")),
        destination.get("fila", -1),
        destination.get("columna", -1),
    )


def ordered_successors(
    state: dict[str, Any], action_order: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Obtener pares acción/estado del motor y ordenarlos para recursión adversarial.
    
    Purpose: Obtener pares acción/estado del motor y ordenarlos para recursión adversarial.
    Preconditions: Estado legal y orden configurado.
    Postconditions: Lista de acciones legales con estados resultantes, reversible en exploración.
    Complexity: O(b log b + b*T), incluye materialización y ordenación.
    AI usage: Yes.
    AI intervention: IA participó en la adaptación de action_successors al árbol adversarial.
    Student validation: Pruebas de equivalencia y orden; revisión individual pendiente.
    """
    pairs = action_successors(state)
    pairs.sort(key=lambda pair: action_key(pair[0]))
    if action_order == "reverse":
        pairs.reverse()
    return pairs



def result_payload(
    algorithm: str,
    action: dict[str, Any] | None,
    value: float,
    requested_depth: int,
    metrics: dict[str, int],
    started_at: float,
    action_order: str,
) -> dict[str, Any]:
    """Serializar decisión adversarial, utilidad y métricas comunes.
    
    Purpose: Serializar decisión adversarial, utilidad y métricas comunes.
    Preconditions: Acción y métricas provenientes de búsqueda ya finalizada.
    Postconditions: Diccionario estable con definiciones de contadores y tiempo.
    Complexity: O(1) más tamaño fijo de datos.
    AI usage: Yes.
    AI intervention: IA ayudó a crear formato de resultados comparables para API e informes.
    Student validation: Métricas reproducidas en experimentos 7–10; revisión individual pendiente.
    """
    return {
        "algorithm": algorithm,
        "action": action,
        "value": value,
        "requested_depth": requested_depth,
        "depth_reached": metrics["depth_reached"],
        "nodes_generated": metrics["nodes_generated"],
        "nodes_visited": metrics["nodes_visited"],
        "nodes_evaluated": metrics["nodes_evaluated"],
        "nodes_pruned": metrics["nodes_pruned"],
        "action_order": action_order,
        "elapsed_seconds": perf_counter() - started_at,
        "metric_definitions": {
            "nodes_generated": "Sucesores legales materializados al expandir nodos; no incluye la raíz.",
            "nodes_visited": "Nodos cuya búsqueda recursiva comenzó; incluye la raíz.",
            "nodes_evaluated": "Hojas terminales o de profundidad límite evaluadas.",
            "nodes_pruned": "Ramas de sucesores inmediatos omitidas tras un corte alfa-beta; no cuenta descendientes hipotéticos.",
        },
    }