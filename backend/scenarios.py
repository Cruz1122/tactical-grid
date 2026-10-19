from copy import deepcopy
from typing import Any

from backend.game.validation import validate_scenario, validate_state


def prepare_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Prepara y valida una copia del estado inicial sin modificar la entrada.

    Copia el escenario, asigna el spawn inicial y activa las unidades que no
    declaran actividad. Recorre el escenario en O(n) tiempo y espacio; no usa IA.
    """
    validate_scenario(scenario)
    state = deepcopy(scenario)
    for unit in state["unidades"]:
        unit["spawn"] = {"fila": unit["fila"], "columna": unit["columna"]}
        unit.setdefault("activo", True)
    validate_state(state)
    return state
