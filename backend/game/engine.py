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
    """Aplicar la captura de una víctima y devolver la reina a su spawn si la portaba.
    
    Purpose: Aplicar la captura de una víctima y devolver la reina a su spawn si la portaba.
    Preconditions: Atacante y víctima activos, bandos distintos, captura legal.
    Postconditions: La víctima queda inactiva hasta la reaparición y la reina vuelve a recurso_spawn si era portador.
    Complexity: O(U) para localizar unidades, además de actualización de estructuras.
    AI usage: Yes.
    AI intervention: IA participó en depuración de capturas; el usuario corrigió una sugerencia errónea de devolver reina a la casilla de captura.
    Student validation: Regla recurso_spawn confirmada por el usuario y pruebas; revisión personal pendiente.
    """
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
    """Reactivar unidades inactivas cuando su spawn original está libre y es legal.
    
    Purpose: Reactivar unidades inactivas cuando su spawn original está libre y es legal.
    Preconditions: Estado interno coherente con spawns guardados.
    Postconditions: Unidades reaparecidas sin superponer ocupación; restantes esperan inactivas.
    Complexity: O(U log U+F*C+K) más conjuntos de ocupación.
    AI usage: Yes.
    AI intervention: IA asistió en implementación de reapariciones y cobertura de casos ocupados.
    Student validation: Pruebas de respawn/capturas aprobadas; revisión personal pendiente.
    """
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
    """Congelar partes invariantes de mapa/costos/bases para búsquedas repetidas.
    
    Purpose: Congelar partes invariantes de mapa/costos/bases para búsquedas repetidas.
    Preconditions: Escenario interno preparado.
    Postconditions: Tupla inmutable del componente estático.
    Complexity: O(S), con S tamaño de la descripción estática del tablero.
    AI usage: Yes.
    AI intervention: IA asistió reducción del trabajo repetido al calcular claves.
    Student validation: Pruebas de determinismo y búsqueda; revisión personal pendiente.
    """
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
    """Codificar deterministamente un estado compuesto para visitados y comparación.
    
    Purpose: Codificar deterministamente un estado compuesto para visitados y comparación.
    Preconditions: Estado interno preparado con unidades identificadas.
    Postconditions: Tupla estable diferenciando turno, posesión, actividad, reyes y resultado.
    Complexity: O(S+U log U+K log K), o excluyendo parte estática precomputada.
    AI usage: Yes.
    AI intervention: IA ayudó a diseñar clave de estados y su reutilización en búsqueda.
    Student validation: Caso 6 de estado compuesto y tests de claves; revisión individual pendiente.
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
    """Aplicar en una copia movimiento, captura, eventual recogida y respawn sin alternar turno.
    
    Purpose: Aplicar en una copia movimiento, captura, eventual recogida y respawn sin alternar turno.
    Preconditions: Destino legal y unidad existente activa.
    Postconditions: Copia con efectos completos, conservando spawn de unidades y reina.
    Complexity: O(U+T_respawn) más comprobación de regla de recogida.
    AI usage: Yes.
    AI intervention: IA ayudó a integrar las consecuencias de acciones para navegación y turnos reales.
    Student validation: Pruebas de efectos hipotéticos y motores; revisión humana pendiente.
    """
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
    """Aplicar sobre una copia el movimiento completo de una unidad sin alternar turnos.
    
    Purpose: Aplicar sobre una copia el movimiento completo de una unidad sin alternar turnos.
    Preconditions: Movimiento legal para la unidad dada.
    Postconditions: Estado hipotético con capturas/recogida resueltas y estado de origen intacto.
    Complexity: O(S+T_move+T_respawn) incluyendo copia y efectos.
    AI usage: Yes.
    AI intervention: IA ayudó a separar navegación hipotética de jugadas adversariales completas.
    Student validation: Pruebas de rutas/capturas; revisión personal pendiente.
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
    """Aplicar una acción real completa y comprobar turno/estado final.
    
    Purpose: Aplicar una acción real completa y comprobar turno/estado final.
    Preconditions: Estado y acción validados conforme al motor.
    Postconditions: Nuevo estado correcto, anterior intacto, turno actualizado o final terminal.
    Complexity: O(S+U+T_move+T_validate), incluye copia y validación.
    AI usage: Yes.
    AI intervention: IA participó en implementación/refinamiento de transiciones, jaques, reina y finales.
    Student validation: Pruebas de atomicidad, turnos y capturas; revisión individual pendiente.
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
    """Exponer la aplicación de un movimiento completo del motor.
    
    Purpose: Exponer la aplicación de un movimiento completo del motor.
    Preconditions: ID de unidad y destino legales.
    Postconditions: Nuevo estado sin tocar original; turno actualizado.
    Complexity: Costo de transición del motor incluyendo copia y validación.
    AI usage: Yes.
    AI intervention: IA asistió integración de movimiento y control de turno.
    Student validation: Pruebas de transiciones; revisión personal pendiente.
    """
    return transition(
        state,
        {"type": "move", "unit_id": unit_id, "destination": destination},
    )


def capture(state: dict[str, Any], attacker_id: str, victim_id: str) -> dict[str, Any]:
    """Aplicar una captura explícita cuando es legal mediante el motor.
    
    Purpose: Aplicar una captura explícita cuando es legal mediante el motor.
    Preconditions: Atacante, víctima y estado válidos.
    Postconditions: Nuevo estado con consecuencias de captura y reaparición.
    Complexity: Costo dominado por transición y validación de estado.
    AI usage: Yes.
    AI intervention: IA contribuyó a implementación y reglas de capturas.
    Student validation: Pruebas de captura y retorno de reina al spawn; revisión humana pendiente.
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
    """Resolver reapariciones sin mutar el estado de entrada.
    
    Purpose: Resolver reapariciones sin mutar el estado de entrada.
    Preconditions: Estado con spawns originales válidos.
    Postconditions: Nuevo estado con unidades reactivadas cuando procede.
    Complexity: O(S+U log U) aproximadamente por copia y comprobación de ocupación.
    AI usage: Yes.
    AI intervention: IA asistió reglas deterministas de reaparición y sus tests.
    Student validation: Casos spawn ocupado y libre; revisión humana pendiente.
    """
    candidate = deepcopy(state)
    _respawn_in_place(candidate)
    validate_state(candidate, check_connectivity=False)
    return candidate


def collect_queen(state: dict[str, Any], unit_id: str) -> dict[str, Any]:
    """Ejecutar recogida explícita legal de reina y consumir turno.
    
    Purpose: Ejecutar recogida explícita legal de reina y consumir turno.
    Preconditions: Unidad autorizada, recurso libre y rey propio sin jaque.
    Postconditions: Nuevo estado con portador y turno correspondiente; sin mutar anterior.
    Complexity: Dominada por transición completa del motor O(S+T_validate).
    AI usage: Yes.
    AI intervention: IA participó en diseño/revisión de acción especial y su integración.
    Student validation: Tests de recogida/jaque; validación personal pendiente.
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
    """Consultar victoria, derrota o empate terminal del estado.
    
    Purpose: Consultar victoria, derrota o empate terminal del estado.
    Preconditions: Estado preparado y juego coherente.
    Postconditions: Identificador del ganador, empate o None si continúa.
    Complexity: O(U) para localizar portador/meta o lectura de resultado según estado.
    AI usage: Yes.
    AI intervention: IA ayudó a revisar reglas terminales y verificación de portador.
    Student validation: Partida 6x6 terminada y pruebas de victoria/empate; revisión personal pendiente.
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
    """Generar pares acción-estado legal de todas las unidades del bando activo.
    
    Purpose: Generar pares acción-estado legal de todas las unidades del bando activo.
    Preconditions: Estado interno válido; partida no terminada.
    Postconditions: Acciones reales y siguientes estados listos para árbol MAX/MIN.
    Complexity: O(b*(S+T_transition)) para b acciones legales.
    AI usage: Yes.
    AI intervention: IA asistió adaptación del motor para Minimax/alfa-beta sin duplicar movimientos.
    Student validation: Experimentos adversariales y pruebas de acciones legales; revisión personal pendiente.
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
    """Entregar estados sucesores oficiales sin necesidad de conservar descripción de acción.
    
    Purpose: Entregar estados sucesores oficiales sin necesidad de conservar descripción de acción.
    Preconditions: Estado válido.
    Postconditions: Lista de estados producidos por acciones legales, sin mutar origen.
    Complexity: O(b*(S+T_transition)) según número de acciones.
    AI usage: Yes.
    AI intervention: IA apoyó diseño de expansión común del motor.
    Student validation: Tests del motor y comparación con action_successors; validación personal pendiente.
    """
    return [next_state for _, next_state in action_successors(state)]


def is_goal(state: dict[str, Any], goal: str | dict[str, Any]) -> bool:
    """Comprobar si una posición o condición objetivo se satisface.
    
    Purpose: Comprobar si una posición o condición objetivo se satisface.
    Preconditions: Estado y objetivo bajo contrato admitido.
    Postconditions: Booleano sin efectos secundarios.
    Complexity: O(U) para buscar unidad/portador según forma de la meta.
    AI usage: Yes.
    AI intervention: IA intervino en definición de condiciones meta de navegación y victoria.
    Student validation: Pruebas de goal y rutas; revisión personal pendiente.
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
    """Instalar reyes opcionales válidos antes de iniciar movimientos.
    
    Purpose: Instalar reyes opcionales válidos antes de iniciar movimientos.
    Preconditions: Posiciones y cantidades compatibles con terreno y unidades.
    Postconditions: Estado con reyes fijos configurados o error atómico.
    Complexity: Dominada por copia y validación O(S+F*C+K).
    AI usage: Yes.
    AI intervention: IA asistió pruebas de reyes opcionales y configuración.
    Student validation: Regresiones de reyes y bloqueo de base; revisión personal pendiente.
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
    """Elegir deterministamente ubicaciones legales de reyes según configuración.
    
    Purpose: Elegir deterministamente ubicaciones legales de reyes según configuración.
    Preconditions: Estado sin inicio de jugadas y cantidades válidas.
    Postconditions: Reyes estáticos no superpuestos ni colocados en bases u obstáculos.
    Complexity: Dependiente de F*C y candidatos evaluados por selección.
    AI usage: Yes.
    AI intervention: IA contribuyó a algoritmo de asignación y testeo de coherencia.
    Student validation: Tests de reyes y configuraciones; validación personal pendiente.
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