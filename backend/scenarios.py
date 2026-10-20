from copy import deepcopy
from typing import Any

from backend.game.engine import check_winner
from backend.game.validation import validate_scenario, validate_state


def prepare_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Prepara y valida una copia del estado inicial sin modificar la entrada.

    Copia el escenario, asigna el spawn inicial y activa las unidades que no
    declaran actividad. Recorre el escenario en O(n) tiempo y espacio.
    """
    validate_scenario(scenario)
    state = deepcopy(scenario)
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
