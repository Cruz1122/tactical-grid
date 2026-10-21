from __future__ import annotations

from time import perf_counter
from typing import Any

from backend.game.engine import action_successors

WIN_SCORE = 100_000
ACTION_ORDERS = ("normal", "reverse")


def validate_search(state: dict[str, Any], depth: int, action_order: str) -> None:
    """Valida explícitamente los parámetros y el turno raíz de la búsqueda."""
    if type(depth) is not int or depth < 0:
        raise ValueError("La profundidad debe ser un entero mayor o igual que cero")
    if action_order not in ACTION_ORDERS:
        raise ValueError("El orden de acciones debe ser 'normal' o 'reverse'")
    if state.get("turno") not in ("A", "B"):
        raise ValueError("El estado debe indicar el turno 'A' o 'B'")


def action_key(action: dict[str, Any]) -> tuple[int, str, int, int]:
    """Define el desempate fijo: movimientos por unidad/destino y luego recogida."""
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
    """Ordena acciones canónicamente; reverse invierte solo el orden de exploración."""
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
    """Construye métricas con contadores definidos igual para ambos algoritmos."""
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
