from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from backend.game.movement import has_legal_action, is_in_check, legal_moves
from backend.game.validation import (
    ScenarioValidationError,
    carrier_winner,
    validate_action,
    validate_state,
)

Position = tuple[int, int]


def _position(value: Any) -> Position:
    if isinstance(value, dict):
        row = value.get("fila", value.get("row"))
        column = value.get("columna", value.get("column"))
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        row, column = value
    else:
        raise ValueError("El destino debe incluir fila y columna")
    if type(row) is not int or type(column) is not int:
        raise ValueError("Las coordenadas de la acción deben ser enteros")
    return row, column


def _position_dict(position: Position) -> dict[str, int]:
    return {"fila": position[0], "columna": position[1]}


def _unit_by_id(state: dict[str, Any], unit_id: str) -> dict[str, Any] | None:
    return next(
        (unit for unit in state.get("unidades", []) if unit.get("id") == unit_id),
        None,
    )


def _ground_queen(state: dict[str, Any]) -> Position | None:
    game = state.get("juego", {})
    queen = state.get("recurso")
    if not isinstance(game, dict) or game.get("portador_recurso") is not None:
        return None
    if not isinstance(queen, dict):
        return None
    try:
        return _position(queen)
    except ValueError:
        return None


def _queen_spawn(state: dict[str, Any]) -> Position | None:
    """Return the queen's immutable original spawn position, if available."""
    try:
        return _position(state.get("recurso_spawn"))
    except ValueError:
        return None


def _capture_unit(
    state: dict[str, Any], attacker_id: str, victim_id: str, position: Position
) -> None:
    attacker = _unit_by_id(state, attacker_id)
    victim = _unit_by_id(state, victim_id)
    if (
        attacker is None
        or victim is None
        or attacker.get("activo", True) is not True
        or victim.get("activo", True) is not True
    ):
        raise ValueError("La captura requiere un atacante y una víctima activos")
    if attacker.get("bando") == victim.get("bando"):
        raise ValueError("No se puede capturar una unidad del mismo bando")

    game = state["juego"]
    if game.get("portador_recurso") == victim_id:
        queen_spawn = _queen_spawn(state)
        if queen_spawn is None:
            raise ValueError("La reina no conserva un spawn original válido")
        game["portador_recurso"] = None
        state["recurso"] = _position_dict(queen_spawn)

    victim["activo"] = False
    victim["fila"] = -1
    victim["columna"] = -1


def _respawn_in_place(state: dict[str, Any]) -> None:
    units = state.get("unidades", [])
    active_positions = {
        (unit["fila"], unit["columna"])
        for unit in units
        if unit.get("activo", True) is True
    }
    king_positions = {
        (king["fila"], king["columna"])
        for kings in state.get("reyes", {}).values()
        if isinstance(kings, list)
        for king in kings
    }
    queen_position = _ground_queen(state)
    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]

    for unit in sorted(units, key=lambda item: item.get("id", "")):
        if unit.get("activo", True) is not False:
            continue
        spawn = unit.get("spawn")
        if not isinstance(spawn, dict):
            continue
        try:
            position = _position(spawn)
        except ValueError:
            continue
        row, column = position
        if not (0 <= row < rows and 0 <= column < columns):
            continue
        terrain_id = state["terreno"][row][column]
        terrain = state["tipos_terreno"].get(terrain_id)
        if not isinstance(terrain, dict) or terrain.get("transitable") is not True:
            continue
        if position in active_positions or position in king_positions or position == queen_position:
            continue
        unit["fila"], unit["columna"] = position
        unit["activo"] = True
        active_positions.add(position)



def _finish(state: dict[str, Any], result: str) -> None:
    state["juego"]["estado"] = "finalizado"
    state["juego"]["resultado"] = result


def _freeze_state_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(
            sorted((key, _freeze_state_value(nested)) for key, nested in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_state_value(item) for item in value)
    return value


def static_state_key(state: dict[str, Any]) -> tuple[Any, ...]:
    """Congela una vez los datos estáticos compartidos por la búsqueda."""
    return _freeze_state_value(
        {
            key: state.get(key)
            for key in (
                "version",
                "mapa",
                "tipos_terreno",
                "terreno",
                "bases",
                "recurso_spawn",
            )
        }
    )


def state_key(
    state: dict[str, Any], *, static_key: tuple[Any, ...] | None = None
) -> tuple[Any, ...]:
    """Produce una clave inmutable y determinista para estados equivalentes.

    Preconditions: el estado contiene estructuras JSON válidas y unidades con IDs.
    Postconditions: la clave considera escenario, turno, unidades/spawns y datos
    adicionales, reina, reyes y fase/resultado; ignora identidades Python y orden
    de claves.
    `static_key`, si se entrega, debe proceder del mismo escenario inmutable.
    Complexity: O(S + U log U + K log K), o O(U log U + K log K) con `static_key`.
    """
    units = tuple(
        sorted(
            (
                unit.get("id"),
                unit.get("bando"),
                unit.get("tipo"),
                unit.get("fila"),
                unit.get("columna"),
                unit.get("activo", True),
                _freeze_state_value(unit.get("spawn")),
                _freeze_state_value(
                    {
                        key: value
                        for key, value in unit.items()
                        if key
                        not in {
                            "id",
                            "bando",
                            "tipo",
                            "fila",
                            "columna",
                            "activo",
                            "spawn",
                        }
                    }
                ),
            )
            for unit in state.get("unidades", [])
        )
    )
    kings = state.get("reyes", {})
    king_positions = tuple(
        (
            side,
            tuple(
                sorted(
                    (king.get("fila"), king.get("columna"))
                    for king in kings.get(side, [])
                )
            ),
        )
        for side in ("A", "B")
    ) if isinstance(kings, dict) else ()
    game = state.get("juego", {})
    game_key = (
        game.get("portador_recurso"),
        game.get("estado"),
        game.get("resultado"),
        _freeze_state_value(
            {
                key: value
                for key, value in game.items()
                if key not in {"portador_recurso", "estado", "resultado"}
            }
        ),
    ) if isinstance(game, dict) else None
    scenario_key = static_key if static_key is not None else static_state_key(state)
    state_extras = _freeze_state_value(
        {
            key: value
            for key, value in state.items()
            if key
            not in {
                "version",
                "mapa",
                "tipos_terreno",
                "terreno",
                "bases",
                "recurso_spawn",
                "turno",
                "unidades",
                "recurso",
                "juego",
                "reyes",
            }
        }
    )
    return (
        scenario_key,
        state.get("turno"),
        units,
        _freeze_state_value(state.get("recurso")),
        game_key,
        king_positions,
        state_extras,
    )


def _apply_move_effects(
    state: dict[str, Any], unit_id: str, destination: Position
) -> None:
    """Aplica movimiento, capturas y recogida de reina sobre una copia mutable."""
    mover = _unit_by_id(state, unit_id)
    if mover is None:
        raise ValueError(f"No existe la unidad {unit_id!r}")

    game = state["juego"]
    victims = [
        unit
        for unit in state.get("unidades", [])
        if unit.get("activo", True) is True
        and unit.get("bando") != mover.get("bando")
        and (unit.get("fila"), unit.get("columna")) == destination
    ]
    captured_carrier = any(
        game.get("portador_recurso") == victim.get("id") for victim in victims
    )
    mover["fila"], mover["columna"] = destination
    for victim in victims:
        _capture_unit(state, unit_id, victim["id"], destination)

    if not captured_carrier and _ground_queen(state) == destination:
        pickup = deepcopy(state)
        pickup["juego"]["portador_recurso"] = unit_id
        pickup["recurso"] = None
        if not is_in_check(pickup, mover["bando"]):
            game["portador_recurso"] = unit_id
            state["recurso"] = None


def hypothetical_move(
    state: dict[str, Any], unit_id: str, destination: dict[str, int] | Position
) -> dict[str, Any]:
    """Devuelve una copia tras un movimiento legal, sin consumir ni alternar turnos.

    Conserva los efectos compartidos de captura, reina y reaparición; no comprueba
    el turno activo ni resuelve el resultado de una partida hipotética.
    """
    target = _position(destination)
    unit = _unit_by_id(state, unit_id)
    if unit is None or unit.get("activo", True) is not True:
        raise ValueError(f"No existe una unidad activa con id {unit_id!r}")
    if _position_dict(target) not in legal_moves(state, unit_id):
        raise ValueError(f"El destino {_position_dict(target)} no es legal para la unidad {unit_id!r}")

    candidate = deepcopy(state)
    _apply_move_effects(candidate, unit_id, target)
    _respawn_in_place(candidate)
    return candidate


def transition(state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    """Aplica una acción legal sobre una copia y devuelve el estado resultante.

    Preconditions: `state` cumple `validate_state`; action es un movimiento o una
    recogida explícita del bando activo.
    Postconditions: la entrada no cambia; el resultado resuelve captura, reina,
    reapariciones, turno y finalización, y vuelve a pasar `validate_state`.
    Complexity: O(U + K*U*max(F,C) + R*C) por turno, dominada por movimiento,
    jaque y validación; espacio O(S + U + K) por la copia independiente.

    """
    validate_action(state, action)
    kind = action.get("type", action.get("tipo", action.get("action")))
    if kind is None:
        kind = "move" if "destination" in action or "destino" in action else "collect"
    kind = {
        "mover": "move",
        "movimiento": "move",
        "recoger": "collect",
        "recoger_reina": "collect",
        "collect_queen": "collect",
    }.get(kind, kind)
    unit_id = cast(str, action.get("unit_id", action.get("unidad_id")))
    candidate = deepcopy(state)
    game = candidate["juego"]
    game["estado"] = "en_curso"

    if kind == "move":
        destination_value = action.get("destination", action.get("destino"))
        destination = _position(destination_value)
        _apply_move_effects(candidate, unit_id, destination)

    elif kind == "collect":
        game["portador_recurso"] = unit_id
        candidate["recurso"] = None
    else:
        raise ValueError(f"Acción desconocida: {kind!r}")

    _respawn_in_place(candidate)
    winner = carrier_winner(candidate)
    if winner is not None:
        _finish(candidate, winner)
    else:
        candidate["turno"] = "B" if state.get("turno") == "A" else "A"
        if not has_legal_action(candidate, candidate["turno"]):
            _finish(candidate, "empate")

    validate_state(candidate, check_connectivity=False)
    return candidate


def apply_move(
    state: dict[str, Any], unit_id: str, destination: dict[str, int] | tuple[int, int]
) -> dict[str, Any]:
    """Ejecuta el movimiento usando la transición común del motor.

    Preconditions: unidad activa del turno y destino en `legal_moves`.
    Postconditions: devuelve un estado independiente o falla sin alterar la entrada.
    Complexity: la misma que `transition`; no duplica reglas.
    """
    return transition(
        state,
        {"type": "move", "unit_id": unit_id, "destination": destination},
    )


def capture(state: dict[str, Any], attacker_id: str, victim_id: str) -> dict[str, Any]:
    """Captura una unidad coincidente y procesa los intentos de reaparición.

    Preconditions: atacante y víctima activos, enemigos y en la misma casilla.
    Postconditions: retorna una copia con víctima inactiva o reaparecida; si era
    portadora, la reina vuelve a su spawn original sin recogida automática y el
    spawn de la víctima permanece intacto.
    Complexity: O(U log U + K) en tiempo y O(S + U) en espacio.
    """
    candidate = deepcopy(state)
    attacker = _unit_by_id(candidate, attacker_id)
    victim = _unit_by_id(candidate, victim_id)
    if attacker is None or victim is None:
        raise ValueError("No existe el atacante o la víctima")
    position = _position(attacker)
    if position != _position(victim):
        raise ValueError("El atacante y la víctima deben compartir casilla para capturar")
    _capture_unit(candidate, attacker_id, victim_id, position)
    _respawn_in_place(candidate)
    validate_state(candidate, check_connectivity=False)
    return candidate


def respawn(state: dict[str, Any]) -> dict[str, Any]:
    """Intenta reactivar las unidades inactivas en orden determinista por ID.

    Preconditions: unidades inactivas conservan un `spawn` válido.
    Postconditions: devuelve una copia; reaparecen solo las que encuentran su
    spawn transitable y libre de unidades activas y reyes.
    Complexity: O(U log U + K) en tiempo y O(U + K) en espacio.
    """
    candidate = deepcopy(state)
    _respawn_in_place(candidate)
    validate_state(candidate, check_connectivity=False)
    return candidate


def collect_queen(state: dict[str, Any], unit_id: str) -> dict[str, Any]:
    """Ejecuta la recogida explícita como una acción que consume turno.

    Preconditions: unidad activa del bando en turno ocupa la reina disponible y
    su rey no está en jaque.
    Postconditions: devuelve una copia con la unidad como portadora, sin desplazarla.
    Complexity: la misma que `transition`.
    """
    return transition(state, {"type": "collect", "unit_id": unit_id})


def check_status(state: dict[str, Any]) -> dict[str, bool]:
    """Calcula el jaque de ambos bandos sin almacenarlo en el estado.

    Preconditions: estado estructuralmente válido.
    Postconditions: devuelve bandos y valores calculados por `is_in_check`.
    Complexity: O(K*U*max(F,C)) en el peor caso; espacio O(U+K).
    """
    return {side: is_in_check(state, side) for side in ("A", "B")}


def check_winner(state: dict[str, Any]) -> str | None:
    """Devuelve ganador, empate o `None` según el estado de partida.

    Preconditions: `state` está preparado para el motor.
    Postconditions: no modifica el estado; detecta portador en su base y empate
    cuando el bando inicial o activo carece de movimiento y recogida legales.
    Complexity: O(U*(U+K*max(F,C))) en el peor caso.
    """
    game = state.get("juego", {})
    if not isinstance(game, dict):
        return None
    if game.get("estado") == "finalizado":
        return game.get("resultado")
    winner = carrier_winner(state)
    if winner is not None:
        return winner
    side = state.get("turno")
    if (
        game.get("estado") in ("configuracion", "en_curso")
        and isinstance(side, str)
        and side in ("A", "B")
        and not has_legal_action(state, side)
    ):
        return "empate"
    return None


def action_successors(
    state: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Genera pares acción/estado usando las reglas y transiciones existentes.

    Preconditions: estado configurado o en curso y con unidades identificadas.
    Postconditions: cada par corresponde a una acción legal del bando activo;
    el estado de entrada no cambia y se incluye la recogida explícita si procede.
    Complexity: O(A*T), con A acciones candidatas y T el costo de `transition`.
    """
    game = state.get("juego", {})
    if not isinstance(game, dict) or game.get("estado") == "finalizado":
        return []
    side = state.get("turno")
    if side not in ("A", "B"):
        return []
    actions: list[dict[str, Any]] = []
    for unit in sorted(state.get("unidades", []), key=lambda item: item.get("id", "")):
        if unit.get("activo", True) is not True or unit.get("bando") != side:
            continue
        unit_id = unit.get("id")
        for destination in legal_moves(state, unit_id):
            actions.append({"type": "move", "unit_id": unit_id, "destination": destination})

    queen = _ground_queen(state)
    if queen is not None and not is_in_check(state, side):
        for unit in sorted(state.get("unidades", []), key=lambda item: item.get("id", "")):
            if (
                unit.get("activo", True) is True
                and unit.get("bando") == side
                and (unit.get("fila"), unit.get("columna")) == queen
            ):
                actions.append({"type": "collect", "unit_id": unit.get("id")})

    return [(action, transition(state, action)) for action in actions]


def successors(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibilidad histórica: devuelve solo los estados sucesores."""
    return [next_state for _, next_state in action_successors(state)]


def is_goal(state: dict[str, Any], goal: str | dict[str, Any]) -> bool:
    """Comprueba exclusivamente un resultado de partida, no una meta de ruta.

    Preconditions: `goal` es un bando/resultado o un objeto con `bando`,
    `resultado` o `ganador`.
    Postconditions: compara el resultado terminal solicitado sin modificar datos.
    Complexity: O(1) tiempo y espacio.
    """
    requested = goal if isinstance(goal, str) else None
    if isinstance(goal, dict):
        requested = goal.get("resultado", goal.get("ganador", goal.get("bando", goal.get("winner"))))
    if requested not in ("A", "B", "empate"):
        return False
    game = state.get("juego", {})
    return isinstance(game, dict) and game.get("estado") == "finalizado" and game.get("resultado") == requested


def configure_kings(
    state: dict[str, Any], kings: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Reemplaza posiciones de reyes durante la configuración previa al juego.

    Preconditions: la partida está en `configuracion` y las posiciones satisfacen
    las reglas de terreno, ocupación, bases y conectividad.
    Postconditions: devuelve una copia validada; un fallo no altera el original.
    Complexity: O(R*C + U + K) en tiempo/espacio.
    """
    game = state.get("juego", {})
    if not isinstance(game, dict) or game.get("estado") != "configuracion":
        raise ValueError("Los reyes solo pueden configurarse antes de iniciar la partida")
    candidate = deepcopy(state)
    candidate["reyes"] = deepcopy(kings)
    validate_state(candidate)
    result = check_winner(candidate)
    if result is not None:
        _finish(candidate, result)
        validate_state(candidate)
    return candidate


def generate_kings(
    state: dict[str, Any], counts: dict[str, int]
) -> dict[str, Any]:
    """Genera ubicaciones de reyes válidas y deterministas según cantidades.

    Preconditions: estado en configuración; `counts` especifica cantidades no
    negativas para A y B.
    Postconditions: reemplaza reyes en una copia usando celdas transitables en
    orden fila-columna. Es determinista y devuelve exactamente las cantidades
    pedidas si su selección voraz encuentra una ubicación; si no, lanza `ValueError`
    sin mutar la entrada. No garantiza encontrar una solución existente.
    Complexity: O(K*(R*C)^2) en el peor caso por las pruebas de configuración;
    espacio O(R*C + U + K).
    """
    game = state.get("juego", {})
    if not isinstance(game, dict) or game.get("estado") != "configuracion":
        raise ValueError("Los reyes solo pueden configurarse antes de iniciar la partida")
    if set(counts) != {"A", "B"} or any(type(counts[side]) is not int or counts[side] < 0 for side in ("A", "B")):
        raise ValueError("Indica cantidades enteras no negativas para A y B")

    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]
    blocked = {
        (unit["fila"], unit["columna"])
        for unit in state.get("unidades", [])
        if unit.get("activo", True) is True
    }
    blocked.update(
        (unit["spawn"]["fila"], unit["spawn"]["columna"])
        for unit in state.get("unidades", [])
        if isinstance(unit.get("spawn"), dict)
    )
    blocked.update(
        (position["fila"], position["columna"])
        for position in state.get("bases", {}).values()
    )
    queen = _ground_queen(state)
    if queen is not None:
        blocked.add(queen)
    candidates = [
        (row, column)
        for row in range(rows)
        for column in range(columns)
        if (row, column) not in blocked
        and state["tipos_terreno"].get(state["terreno"][row][column], {}).get("transitable") is True
    ]

    selected: dict[str, list[dict[str, Any]]] = {"A": [], "B": []}
    remaining = dict(counts)
    for side in ("A", "B"):
        while remaining[side] > 0:
            accepted = False
            occupied = {
                (king["fila"], king["columna"])
                for side_kings in selected.values()
                for king in side_kings
            }
            for row, column in candidates:
                if (row, column) in occupied:
                    continue
                trial_kings = deepcopy(selected)
                trial_kings[side].append(
                    {"id": f"{side}_REY_{len(trial_kings[side]) + 1}", "fila": row, "columna": column}
                )
                trial = deepcopy(state)
                trial["reyes"] = trial_kings
                try:
                    validate_state(trial)
                except ScenarioValidationError:
                    continue
                selected = trial_kings
                remaining[side] -= 1
                accepted = True
                break
            if not accepted:
                raise ValueError(
                    f"No hay suficientes posiciones válidas para generar los reyes solicitados de {side}"
                )
    return configure_kings(state, selected)
