from copy import deepcopy
from typing import Any

from backend.game.engine import check_winner
from backend.game.validation import (
    SUPPORTED_UNIT_TYPES,
    validate_scenario,
    validate_state,
)


def prepare_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Copiar y preparar JSON externo, normalizando tipo genérico a estándar y preservando spawns.
    
    Purpose: Copiar y preparar JSON externo, normalizando tipo genérico a estándar y preservando spawns.
    Preconditions: Objeto JSON acorde con campos obligatorios del profesor.
    Postconditions: Estado interno validado y enriquecido o error sin mutar escenario original.
    Complexity: O(F*C+U+K) más validaciones según conectividad.
    AI usage: Yes.
    AI intervention: IA asistió diseño/implementación de carga, normalización y prueba de escenarios.
    Student validation: Validación del tipo genérico acordado por el usuario y tests de JSON; revisión individual pendiente.
    """
    state = deepcopy(scenario)
    units = state.get("unidades") if isinstance(state, dict) else None
    if isinstance(units, list):
        for unit in units:
            if not isinstance(unit, dict):
                continue
            unit_type = unit.get("tipo")
            if (
                isinstance(unit_type, str)
                and unit_type.strip()
                and unit_type not in SUPPORTED_UNIT_TYPES
            ):
                unit["tipo"] = "estandar"
    validate_scenario(state)
    resource_spawn = state.get("recurso_spawn") or state.get("recurso")
    if resource_spawn is not None:
        state["recurso_spawn"] = deepcopy(resource_spawn)
    for unit in state["unidades"]:
        initial_position = {"fila": unit["fila"], "columna": unit["columna"]}
        unit["spawn"] = initial_position
        unit.setdefault("activo", True)
        if unit["activo"] is False:
            unit["fila"] = -1
            unit["columna"] = -1

    game = state["juego"]
    game["estado"] = "configuracion"
    game["resultado"] = None
    if game.get("portador_recurso") is not None:
        state["recurso"] = None

    result = check_winner(state)
    if result is not None:
        game["estado"] = "finalizado"
        game["resultado"] = result

    validate_state(state)
    return state