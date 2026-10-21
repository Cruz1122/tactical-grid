from __future__ import annotations

from typing import Any

Position = tuple[int, int]
PositionLike = dict[str, int] | Position

_UNIT_TYPE_ALIASES = {
    "knight": "knight",
    "caballo": "knight",
    "rook": "rook",
    "torre": "rook",
    "bishop": "bishop",
    "alfil": "bishop",
    "estandar": "estandar",
}
_KNIGHT_OFFSETS = (
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
)
_ORTHOGONAL_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DIAGONAL_DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))


def _position_tuple(position: PositionLike) -> Position:
    if isinstance(position, dict):
        row, column = position.get("fila"), position.get("columna")
    elif isinstance(position, tuple) and len(position) == 2:
        row, column = position
    else:
        raise TypeError("La posición debe contener fila y columna enteras")

    if type(row) is not int or type(column) is not int:
        raise TypeError("La posición debe contener fila y columna enteras")
    return row, column


def _position_dict(position: Position) -> dict[str, int]:
    return {"fila": position[0], "columna": position[1]}


def _inside_board(state: dict[str, Any], position: Position) -> bool:
    row, column = position
    board = state.get("mapa", {})
    return (
        type(board.get("filas")) is int
        and type(board.get("columnas")) is int
        and 0 <= row < board["filas"]
        and 0 <= column < board["columnas"]
    )


def terrain_cost(state: dict[str, Any], position: PositionLike) -> float:
    """Leer del JSON el costo positivo de entrar a una casilla transitable.
    
    Purpose: Leer del JSON el costo positivo de entrar a una casilla transitable.
    Preconditions: Posición dentro del mapa y terreno definido.
    Postconditions: Valor positivo o excepción informativa ante bloqueo/costo inválido.
    Complexity: O(1) acceso a matriz y catálogo.
    AI usage: Yes.
    AI intervention: IA participó en codificación/revisión de costos y pruebas de variación de pantano.
    Student validation: Casos de costos y 177 tests globales; validación individual pendiente.
    """
    row, column = _position_tuple(position)
    coordinate = (row, column)
    if not _inside_board(state, coordinate):
        raise ValueError(f"La posición ({row}, {column}) está fuera del mapa")

    terrain = state.get("terreno")
    if not isinstance(terrain, list) or row >= len(terrain):
        raise ValueError(f"No hay terreno definido para la posición ({row}, {column})")
    terrain_row = terrain[row]
    if not isinstance(terrain_row, list) or column >= len(terrain_row):
        raise ValueError(f"No hay terreno definido para la posición ({row}, {column})")

    terrain_id = terrain_row[column]
    definition = state.get("tipos_terreno", {}).get(terrain_id)
    if not isinstance(definition, dict) or definition.get("transitable") is not True:
        raise ValueError(f"La posición ({row}, {column}) no es transitable")

    cost = definition.get("costo")
    if not isinstance(cost, (int, float)) or isinstance(cost, bool):
        raise TypeError(f"El terreno de la posición ({row}, {column}) no tiene un costo válido")
    return float(cost)


def _active_units(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        unit
        for unit in state.get("unidades", [])
        if isinstance(unit, dict) and unit.get("activo", True) is True
    ]


def _king_positions(state: dict[str, Any]) -> set[Position]:
    positions: set[Position] = set()
    king_groups = state.get("reyes", {})
    if not isinstance(king_groups, dict):
        return positions

    for kings in king_groups.values():
        if not isinstance(kings, list):
            continue
        for king in kings:
            if not isinstance(king, dict):
                continue
            try:
                positions.add(_position_tuple(king))
            except (TypeError, ValueError):
                continue
    return positions


def _ground_queen_position(state: dict[str, Any]) -> Position | None:
    game = state.get("juego", {})
    if isinstance(game, dict) and game.get("portador_recurso") is not None:
        return None
    queen = state.get("recurso")
    if not isinstance(queen, dict):
        return None
    try:
        position = _position_tuple(queen)
    except (TypeError, ValueError):
        return None
    return position if _inside_board(state, position) else None


def _unit_positions(
    units: list[dict[str, Any]], excluded_unit_id: str | None = None
) -> dict[Position, dict[str, Any]]:
    occupied: dict[Position, dict[str, Any]] = {}
    for unit in units:
        if unit.get("id") == excluded_unit_id:
            continue
        try:
            position = _position_tuple(unit)
        except (TypeError, ValueError):
            continue
        occupied[position] = unit
    return occupied


def _is_transitable(state: dict[str, Any], position: Position) -> bool:
    if not _inside_board(state, position):
        return False
    row, column = position
    terrain = state.get("terreno")
    if not isinstance(terrain, list) or row >= len(terrain):
        return False
    terrain_row = terrain[row]
    if not isinstance(terrain_row, list) or column >= len(terrain_row):
        return False
    terrain_id = terrain_row[column]
    terrain_types = state.get("tipos_terreno", {})
    definition = terrain_types.get(terrain_id) if isinstance(terrain_types, dict) else None
    return isinstance(definition, dict) and definition.get("transitable") is True


def _is_square_attacked(
    state: dict[str, Any],
    square: Position,
    attacking_side: str,
    units: list[dict[str, Any]],
    kings: set[Position],
    queen: Position | None,
) -> bool:
    """Determinar si una casilla es atacada por un bando según geometrías de piezas.
    
    Purpose: Determinar si una casilla es atacada por un bando según geometrías de piezas.
    Preconditions: Estado válido y coordenada interior.
    Postconditions: Booleano usado en el cálculo del jaque.
    Complexity: O(U*(F+C)) peor caso por rayos de torre/alfil.
    AI usage: Yes.
    AI intervention: IA asistió implementación/revisión de amenazas sin jaque mate tradicional.
    Student validation: Casos de torre, alfil y caballo en jaque; revisión humana pendiente.
    """
    occupied = _unit_positions(units)
    for unit in units:
        if unit.get("bando") != attacking_side:
            continue
        try:
            origin = _position_tuple(unit)
        except (TypeError, ValueError):
            continue
        row_delta = square[0] - origin[0]
        column_delta = square[1] - origin[1]
        raw_type = unit.get("tipo")
        unit_type = _UNIT_TYPE_ALIASES.get(raw_type) if isinstance(raw_type, str) else None

        if unit_type == "knight":
            if (row_delta, column_delta) in _KNIGHT_OFFSETS:
                return True
            continue
        if unit_type == "estandar":
            if abs(row_delta) + abs(column_delta) == 1:
                return True
            continue

        rook_line = unit_type == "rook" and ((row_delta == 0) != (column_delta == 0))
        bishop_line = (
            unit_type == "bishop"
            and abs(row_delta) == abs(column_delta)
            and row_delta != 0
        )
        if not (rook_line or bishop_line):
            continue
        row_step = (row_delta > 0) - (row_delta < 0)
        column_step = (column_delta > 0) - (column_delta < 0)

        cursor = (origin[0] + row_step, origin[1] + column_step)
        blocked = False
        while cursor != square:
            if (
                not _is_transitable(state, cursor)
                or cursor in kings
                or cursor in occupied
                or cursor == queen
            ):
                blocked = True
                break
            cursor = (cursor[0] + row_step, cursor[1] + column_step)
        if not blocked:
            return True
    return False


def is_in_check(
    state: dict[str, Any],
    side: str,
    hypothetical_move: tuple[str, PositionLike] | None = None,
) -> bool:
    """Calcular amenaza al rey fijo de un equipo según ataques de piezas enemigas.
    
    Purpose: Calcular amenaza al rey fijo de un equipo según ataques de piezas enemigas.
    Preconditions: Estado con reyes opcionales y posiciones coherentes.
    Postconditions: Booleano, sin aplicar jugada ni cambiar el estado.
    Complexity: O(U*(F+C)) peor caso con ataques deslizantes.
    AI usage: Yes.
    AI intervention: IA asistió diseño/revisión del cálculo de jaque y pruebas de capturas.
    Student validation: Casos de rey y prohibición de recoger; validación humana pendiente.
    """
    if side not in ("A", "B"):
        raise ValueError("El bando debe ser 'A' o 'B'")

    units = _active_units(state)
    if hypothetical_move is not None:
        mover_id, requested_position = hypothetical_move
        destination = _position_tuple(requested_position)
        if not _inside_board(state, destination) or not _is_transitable(state, destination):
            raise ValueError("El destino hipotético debe ser una casilla transitable del mapa")

        mover = next((unit for unit in units if unit.get("id") == mover_id), None)
        if mover is None:
            raise ValueError(f"No existe una unidad activa con id {mover_id!r}")
        moved_units: list[dict[str, Any]] = []
        for unit in units:
            if unit.get("id") == mover_id:
                moved_units.append(
                    {**unit, "fila": destination[0], "columna": destination[1]}
                )
                continue
            try:
                other_position = _position_tuple(unit)
            except (TypeError, ValueError):
                moved_units.append(unit)
                continue
            if other_position == destination and unit.get("bando") != mover.get("bando"):
                continue
            moved_units.append(unit)
        units = moved_units

    king_groups = state.get("reyes", {})
    if not isinstance(king_groups, dict):
        return False
    kings_for_side = king_groups.get(side, [])
    if not isinstance(kings_for_side, list):
        return False

    kings = _king_positions(state)
    queen = _ground_queen_position(state)
    enemy_side = "B" if side == "A" else "A"
    for king in kings_for_side:
        if not isinstance(king, dict):
            continue
        try:
            king_position = _position_tuple(king)
        except (TypeError, ValueError):
            continue
        if _is_square_attacked(state, king_position, enemy_side, units, kings, queen):
            return True
    return False


def legal_moves(state: dict[str, Any], unit_id: str) -> list[dict[str, int]]:
    """Enumerar destinos que una unidad activa puede alcanzar legalmente con su geometría.
    
    Purpose: Enumerar destinos que una unidad activa puede alcanzar legalmente con su geometría.
    Preconditions: Estado válido, identificador de unidad existente.
    Postconditions: Lista sin destinos sobre obstáculo/rey/aliado, con capturas enemigas permitidas.
    Complexity: O(F+C) para líneas deslizantes; O(1) geometría básica, más comprobaciones de ocupación.
    AI usage: Yes.
    AI intervention: IA apoyó generación/revisión de movimientos, bloqueos, capturas y pruebas de piezas.
    Student validation: Pruebas de movimientos y bordes; revisión individual pendiente.
    """
    units = _active_units(state)
    unit = next((candidate for candidate in units if candidate.get("id") == unit_id), None)
    if unit is None:
        return []

    raw_type = unit.get("tipo")
    side = unit.get("bando")
    if not isinstance(raw_type, str) or side not in ("A", "B"):
        return []
    unit_type = _UNIT_TYPE_ALIASES.get(raw_type)
    if unit_type is None:
        return []
    try:
        origin = _position_tuple(unit)
    except (TypeError, ValueError):
        return []
    if not _is_transitable(state, origin):
        return []

    occupied = _unit_positions(units, excluded_unit_id=unit_id)
    kings = _king_positions(state)
    queen = _ground_queen_position(state)
    queen_pickup_allowed: bool | None = None

    def can_land(position: Position) -> bool:
        nonlocal queen_pickup_allowed
        if not _is_transitable(state, position) or position in kings:
            return False
        occupant = occupied.get(position)
        if occupant is not None and occupant.get("bando") == unit.get("bando"):
            return False
        if position == queen and occupant is None:
            if queen_pickup_allowed is None:
                queen_pickup_allowed = not is_in_check(
                    state, side, (unit_id, position)
                )
            if not queen_pickup_allowed:
                return False
        return True

    destinations: list[Position] = []
    if unit_type == "knight":
        for row_delta, column_delta in _KNIGHT_OFFSETS:
            candidate = (origin[0] + row_delta, origin[1] + column_delta)
            if _inside_board(state, candidate) and can_land(candidate):
                destinations.append(candidate)
    elif unit_type == "estandar":
        for row_delta, column_delta in _ORTHOGONAL_DIRECTIONS:
            candidate = (origin[0] + row_delta, origin[1] + column_delta)
            if _inside_board(state, candidate) and can_land(candidate):
                destinations.append(candidate)
    else:
        directions = (
            _ORTHOGONAL_DIRECTIONS if unit_type == "rook" else _DIAGONAL_DIRECTIONS
        )
        for row_step, column_step in directions:
            candidate = (origin[0] + row_step, origin[1] + column_step)
            while _inside_board(state, candidate):
                if not _is_transitable(state, candidate) or candidate in kings:
                    break
                occupant = occupied.get(candidate)
                if occupant is not None and occupant.get("bando") == unit.get("bando"):
                    break

                if candidate == queen:
                    if occupant is not None:
                        destinations.append(candidate)
                    else:
                        if queen_pickup_allowed is None:
                            queen_pickup_allowed = not is_in_check(
                                state, side, (unit_id, candidate)
                            )
                        if queen_pickup_allowed:
                            destinations.append(candidate)
                    break

                destinations.append(candidate)
                if occupant is not None:
                    break
                candidate = (candidate[0] + row_step, candidate[1] + column_step)

    return [_position_dict(position) for position in destinations]


def has_legal_action(state: dict[str, Any], side: str) -> bool:
    """Determinar si un equipo dispone de alguna acción legal.
    
    Purpose: Determinar si un equipo dispone de alguna acción legal.
    Preconditions: Estado válido y bando A/B.
    Postconditions: Booleano usado para detectar inmovilidad terminal.
    Complexity: O(U*(F+C)) aproximado en peor caso.
    AI usage: Yes.
    AI intervention: IA contribuyó a comprobaciones de bloqueo y acción de recogida.
    Student validation: Pruebas de finalización sin movimientos; revisión individual pendiente.
    """
    if side not in ("A", "B"):
        return False
    units = _active_units(state)
    for unit in units:
        unit_id = unit.get("id")
        if unit.get("bando") == side and isinstance(unit_id, str) and legal_moves(state, unit_id):
            return True

    queen = _ground_queen_position(state)
    if queen is None or is_in_check(state, side):
        return False
    return any(
        unit.get("bando") == side
        and _position_tuple(unit) == queen
        for unit in units
    )


def move_cost(
    state: dict[str, Any], unit_id: str, destination: PositionLike
) -> float:
    """Calcular costo real de una acción legal, sumando casillas atravesadas cuando corresponde.
    
    Purpose: Calcular costo real de una acción legal, sumando casillas atravesadas cuando corresponde.
    Preconditions: Movimiento legal y catálogo de terrenos positivo.
    Postconditions: Caballo/estándar pagan destino; torre/alfil suman recorrido excluyendo origen.
    Complexity: O(L) con L longitud del desplazamiento para deslizantes; O(1) en otras piezas.
    AI usage: Yes.
    AI intervention: IA ayudó en implementación y corrección de fórmulas de terreno del motor.
    Student validation: Comparaciones BFS/UCS y pruebas de distintos costos; validación individual pendiente.
    """
    target = _position_tuple(destination)
    unit = next(
        (
            candidate
            for candidate in _active_units(state)
            if candidate.get("id") == unit_id
        ),
        None,
    )
    if unit is None:
        raise ValueError(f"No existe una unidad activa con id {unit_id!r}")

    target_dict = _position_dict(target)
    if target_dict not in legal_moves(state, unit_id):
        raise ValueError(f"El destino {target_dict} no es legal para la unidad {unit_id!r}")

    raw_type = unit.get("tipo")
    unit_type = _UNIT_TYPE_ALIASES.get(raw_type) if isinstance(raw_type, str) else None
    if unit_type in ("knight", "estandar"):
        return terrain_cost(state, target)

    origin = _position_tuple(unit)
    row_step = (target[0] > origin[0]) - (target[0] < origin[0])
    column_step = (target[1] > origin[1]) - (target[1] < origin[1])
    cost = 0.0
    cursor = (origin[0] + row_step, origin[1] + column_step)
    while True:
        cost += terrain_cost(state, cursor)
        if cursor == target:
            return cost
        cursor = (cursor[0] + row_step, cursor[1] + column_step)


def apply_move(state: dict, unit_id: str, destination: dict) -> dict:
    """Wrapper compatible con las importaciones históricas del motor."""
    from backend.game.engine import apply_move as execute_move

    return execute_move(state, unit_id, destination)


def capture(state: dict, attacker_id: str, victim_id: str) -> dict:
    """Wrapper compatible; las reglas de captura viven en el motor central."""
    from backend.game.engine import capture as execute_capture

    return execute_capture(state, attacker_id, victim_id)


def respawn(state: dict) -> dict:
    """Wrapper compatible para reapariciones deterministas."""
    from backend.game.engine import respawn as execute_respawn

    return execute_respawn(state)


def check_status(state: dict) -> dict:
    """Wrapper compatible para consultar jaques calculados, no almacenados."""
    from backend.game.engine import check_status as get_status

    return get_status(state)


def collect_queen(state: dict, unit_id: str) -> dict:
    """Wrapper compatible para la recogida explícita de la reina."""
    from backend.game.engine import collect_queen as collect

    return collect(state, unit_id)


def check_winner(state: dict) -> str | None:
    """Wrapper compatible para consultar el resultado de la partida."""
    from backend.game.engine import check_winner as get_winner

    return get_winner(state)