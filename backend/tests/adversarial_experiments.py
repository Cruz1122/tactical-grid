"""Imprime métricas reproducibles para los experimentos adversariales 7–10."""

from __future__ import annotations

import json
from typing import Any

from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.minimax import minimax
from backend.tests.test_adversarial import tactical_state


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    """Selecciona los campos comparables y conserva los tiempos medidos."""
    return {
        "action": result["action"],
        "value": result["value"],
        "requested_depth": result["requested_depth"],
        "depth_reached": result["depth_reached"],
        "nodes_generated": result["nodes_generated"],
        "nodes_visited": result["nodes_visited"],
        "nodes_evaluated": result["nodes_evaluated"],
        "nodes_pruned": result["nodes_pruned"],
        "elapsed_seconds": result["elapsed_seconds"],
    }


def run_experiments() -> dict[str, Any]:
    """Ejecuta los casos con la misma posición inicial de 6x6."""
    state = tactical_state()
    return {
        "case_7_decision": {
            "depth_1_approach": summarize(minimax(state, 1)),
            "depth_2_intercept": summarize(minimax(state, 2)),
        },
        "case_8_minimax_vs_alpha_beta": {
            "minimax": summarize(minimax(state, 3)),
            "alpha_beta": summarize(alpha_beta(state, 3, "normal")),
        },
        "case_9_action_order": {
            "normal": summarize(alpha_beta(state, 3, "normal")),
            "reverse": summarize(alpha_beta(state, 3, "reverse")),
        },
        "case_10_depth": {
            str(depth): summarize(minimax(state, depth)) for depth in (1, 2, 3, 4)
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_experiments(), ensure_ascii=False, indent=2))
