from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.minimax import minimax
from backend.game.engine import hypothetical_move
from backend.game.movement import legal_moves, move_cost
from backend.game.validation import (
    ScenarioValidationError,
    validate_action,
    validate_state,
)


def _position(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    row = value.get("fila", value.get("row"))
    column = value.get("columna", value.get("column"))
    if type(row) is not int or type(column) is not int:
        return None
    return {"fila": row, "columna": column}


def _unit_position(state: dict[str, Any], unit_id: str) -> dict[str, int] | None:
    unit = next(
        (
            candidate
            for candidate in state.get("unidades", [])
            if isinstance(candidate, dict) and candidate.get("id") == unit_id
        ),
        None,
    )
    if unit is None:
        return None
    return _position(unit)


def verify_path(scenario: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Reproduce una ruta encontrada y contrasta su costo sin mutar la entrada.

    La verificación prueba legalidad y coherencia de un testigo positivo. Un
    resultado ``found=false`` no constituye por sí solo una prueba de
    inalcanzabilidad, por lo que se informa esa limitación explícitamente.
    

    Purpose: Reproducir y comprobar cada movimiento de una ruta calculada.
    Preconditions: Ruta, unidad y escenario suministrados.
    Postconditions: Confirma legalidad, costo y objetivo o informa la discrepancia.
    Complexity: O(P*T), P pasos y T costo de transición hipotética.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    errors: list[str] = []
    checks: dict[str, bool] = {}
    if not isinstance(result, dict):
        return {
            "valid": False,
            "errors": ["El resultado de búsqueda debe ser un objeto."],
            "checks": checks,
        }

    try:
        validate_state(scenario)
    except ScenarioValidationError as error:
        return {"valid": False, "errors": error.errors, "checks": checks}

    original = deepcopy(scenario)
    raw_config = scenario.get("prueba")
    config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
    unit_id = result.get("unit_id", config.get("unidad_inicio"))
    if not isinstance(unit_id, str) or not unit_id:
        errors.append("El resultado no identifica la unidad de la ruta.")
    path = result.get("path")
    if not isinstance(path, list):
        errors.append("result.path debe ser una lista.")
        path = []

    found = result.get("found")
    if not isinstance(found, bool):
        errors.append("result.found debe ser booleano.")
    if found is False:
        if path:
            errors.append("Una búsqueda sin solución no puede incluir una ruta.")
        if result.get("cost") is not None or result.get("moves") is not None:
            errors.append("Una búsqueda sin solución debe tener costo y movimientos null.")
        checks["input_unchanged"] = scenario == original
        return {
            "valid": not errors,
            "errors": errors,
            "checks": checks,
            "limitation": "No se certifica inalcanzabilidad sin ejecutar un oráculo completo.",
        }

    if errors or found is not True:
        checks["input_unchanged"] = scenario == original
        return {"valid": False, "errors": errors, "checks": checks}

    assert isinstance(unit_id, str)
    current = deepcopy(scenario)
    start = _unit_position(current, unit_id)
    normalized_path = [_position(step) for step in path]
    if any(step is None for step in normalized_path):
        errors.append("Cada paso de result.path debe incluir fila y columna enteras.")
    elif not normalized_path or normalized_path[0] != start:
        errors.append("La ruta debe comenzar en la posición actual de la unidad.")

    observed_cost = 0.0
    if not errors:
        for index, destination in enumerate(normalized_path[1:], start=1):
            assert destination is not None
            if destination not in legal_moves(current, unit_id):
                errors.append(f"El paso {index} hacia {destination} no es legal.")
                break
            observed_cost += move_cost(current, unit_id, destination)
            current = hypothetical_move(current, unit_id, destination)

    observed_moves = max(0, len(path) - 1)
    checks["moves_match"] = result.get("moves") == observed_moves
    if not checks["moves_match"]:
        errors.append(
            f"result.moves={result.get('moves')!r} no coincide con {observed_moves}."
        )
    reported_cost = result.get("cost")
    checks["cost_matches"] = (
        isinstance(reported_cost, (int, float))
        and not isinstance(reported_cost, bool)
        and math.isclose(
            float(reported_cost), observed_cost, rel_tol=1e-9, abs_tol=1e-9
        )
    )
    if not checks["cost_matches"]:
        errors.append(
            f"result.cost={reported_cost!r} no coincide con el costo reproducido {observed_cost}."
        )

    goal = _position(result.get("goal")) or _position(config.get("objetivo"))
    if goal is not None and normalized_path and normalized_path[-1] != goal:
        errors.append("La ruta no termina en el objetivo declarado.")
        checks["goal_reached"] = False
    elif goal is not None:
        checks["goal_reached"] = True
    checks["input_unchanged"] = scenario == original
    return {
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "observed_moves": observed_moves,
        "observed_cost": observed_cost,
    }


def verify_state(state: dict[str, Any]) -> dict[str, Any]:
    """Valida todas las invariantes estructurales del estado sin modificarlo.

    Purpose: Verificar coherencia de un estado mediante las invariantes del motor.
    Preconditions: Estado serializable y preparado o diagnosticable.
    Postconditions: Retorna informe de validación sin modificar entrada.
    Complexity: Dominada por validación del estado; típicamente O(F*C+U+K).
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    original = deepcopy(state)
    errors: list[str] = []
    try:
        validate_state(state)
    except ScenarioValidationError as error:
        errors.extend(error.errors)
    return {
        "valid": not errors,
        "errors": errors,
        "checks": {"input_unchanged": state == original},
    }


def verify_decision(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Recalcula una decisión adversarial bajo los mismos parámetros y la compara."""
    errors: list[str] = []
    checks: dict[str, bool] = {}
    if not isinstance(result, dict):
        return {
            "valid": False,
            "errors": ["El resultado adversarial debe ser un objeto."],
            "checks": checks,
        }

    original = deepcopy(state)
    try:
        validate_state(state)
    except ScenarioValidationError as error:
        return {"valid": False, "errors": error.errors, "checks": checks}

    algorithm = result.get("algorithm")
    depth = result.get("requested_depth")
    action_order = result.get("action_order", "normal")
    if algorithm not in ("minimax", "alpha_beta"):
        errors.append("El algoritmo debe ser 'minimax' o 'alpha_beta'.")
    if type(depth) is not int or depth < 0:
        errors.append("requested_depth debe ser un entero mayor o igual que cero.")
    if action_order not in ("normal", "reverse"):
        errors.append("action_order debe ser 'normal' o 'reverse'.")

    action = result.get("action")
    if action is not None:
        try:
            validate_action(state, action)
            checks["action_legal"] = True
        except (TypeError, ValueError) as error:
            checks["action_legal"] = False
            errors.append(f"La acción recomendada no es legal: {error}")
    else:
        checks["action_legal"] = (
            depth == 0 or state.get("juego", {}).get("estado") == "finalizado"
        )

    if not errors:
        assert type(depth) is int
        search = minimax if algorithm == "minimax" else alpha_beta
        expected = search(state, depth, action_order)
        checks["action_matches"] = result.get("action") == expected["action"]
        reported_value = result.get("value")
        checks["value_matches"] = (
            isinstance(reported_value, (int, float))
            and not isinstance(reported_value, bool)
            and math.isclose(
                float(reported_value), float(expected["value"]),
                rel_tol=1e-9, abs_tol=1e-9,
            )
        )
        if not checks["action_matches"]:
            errors.append("La acción no coincide con el recálculo adversarial.")
        if not checks["value_matches"]:
            errors.append("El valor no coincide con el recálculo adversarial.")

    for field in (
        "depth_reached",
        "nodes_generated",
        "nodes_visited",
        "nodes_evaluated",
        "nodes_pruned",
    ):
        value = result.get(field)
        if type(value) is not int or value < 0:
            errors.append(f"{field} debe ser un entero no negativo.")
    checks["input_unchanged"] = state == original
    return {"valid": not errors, "errors": errors, "checks": checks}