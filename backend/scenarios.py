from copy import deepcopy
from typing import Any

from backend.game.engine import check_winner
from backend.game.validation import (
    SUPPORTED_UNIT_TYPES,
    validate_scenario,
    validate_state,
)


def prepare_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Prepara y valida una copia del estado inicial sin modificar la entrada.

    Copia el escenario, mapea nombres genéricos de pieza a `estandar`, asigna el
    spawn inicial y activa las unidades que no declaran actividad.
    Recorre el escenario en O(n) tiempo y espacio.
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
