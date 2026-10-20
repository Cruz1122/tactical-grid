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
    """Consulta el costo de terreno de una casilla.

    Precondiciones: `state` contiene dimensiones, matriz y catálogo de terrenos
    coherentes; `position` usa coordenadas enteras dentro del mapa y es transitable.
    Postcondiciones: devuelve el costo configurado como `float` y no modifica el estado.
    Complejidad: O(1) en tiempo y espacio.
    IA en ejecución: no utiliza; consulta datos y reglas deterministas.

    Raises:
        TypeError: si las coordenadas o el costo no tienen tipo válido.
        ValueError: si la posición está fuera del mapa o no es transitable.
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
    """Indica si un bando tiene algún rey amenazado en el estado indicado.

    `hypothetical_move`, si se proporciona, proyecta una jugada sin modificar
    `state`: la unidad activa se desplaza y una unidad enemiga en el destino se
    considera capturada. Esta interfaz permite que el motor de transiciones de la
    fase 3 reutilice la misma regla de jaque.

    Precondiciones: el estado tiene posiciones y tipos de unidad válidos; `side`
    es `A` o `B`; el movimiento hipotético identifica una unidad activa y un destino.
    Postcondiciones: devuelve si algún rey del bando está amenazado; el estado y sus
    unidades originales permanecen intactos. Sin reyes, devuelve `False`.
    Complejidad: O(K * U * max(F, C)) en el peor caso, donde K es el número de
    reyes, U el de unidades, F las filas y C las columnas; espacio O(U + K).
    IA en ejecución: no utiliza; evalúa patrones geométricos deterministas.

    Raises:
        TypeError: si las coordenadas del destino no son enteras.
        ValueError: si el movimiento hipotético referencia una unidad inactiva o
            inexistente, o una posición fuera del mapa/no transitable.
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
    """Genera los destinos disponibles para una unidad sin alterar el estado.

    Precondiciones: `state` describe un tablero coherente y `unit_id` identifica
    una unidad; las unidades inactivas o de tipo desconocido se tratan como sin
    movimientos disponibles.
    Postcondiciones: devuelve coordenadas `{fila, columna}` dentro del mapa que
    respetan terreno, ocupación y patrón de movimiento. Para un destino en la reina,
    el jaque se comprueba sobre la posición hipotética posterior al movimiento.
    No modifica el estado.
    Complejidad: O(U + K + F + C) sin evaluar una recogida; si la reina es un
    destino candidato, el cálculo adicional de jaque cuesta hasta O(K * U *
    max(F, C)). Espacio O(U + K + F + C), incluida la lista de destinos.
    IA en ejecución: no utiliza; aplica reglas deterministas del juego.
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
        if position == queen:
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


def move_cost(
    state: dict[str, Any], unit_id: str, destination: PositionLike
) -> float:
    """Calcula el costo de un destino legal sin alterar el estado.

    Precondiciones: `state` contiene un escenario coherente; `unit_id` identifica
    una unidad activa y `destination` pertenece a `legal_moves(state, unit_id)`.
    Postcondiciones: devuelve el costo del terreno destino para caballo/estándar,
    o la suma de casillas recorridas (sin origen) para torre/alfil. No modifica el
    estado.
    Complejidad: O(U + K + F + C + D) sin comprobar una recogida; si el destino
    es la reina, se añade hasta O(K * U * max(F, C)) para verificar el jaque
    posterior al movimiento. D es la longitud del desplazamiento.
    IA en ejecución: no utiliza; aplica patrones y costos deterministas.

    Raises:
        TypeError: si las coordenadas no son enteras.
        ValueError: si la unidad no está activa o el destino no es legal.
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
    raise NotImplementedError


def capture(state: dict, attacker_id: str, victim_id: str) -> dict:
    raise NotImplementedError


def respawn(state: dict) -> dict:
    raise NotImplementedError


def check_status(state: dict) -> dict:
    raise NotImplementedError


def collect_queen(state: dict, unit_id: str) -> dict:
    raise NotImplementedError


def check_winner(state: dict) -> str | None:
    raise NotImplementedError
