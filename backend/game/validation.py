import math
from typing import Any, TypeGuard

from backend.game.movement import has_legal_action, is_in_check, move_cost

SUPPORTED_UNIT_TYPES = {"knight", "rook", "bishop", "estandar", "caballo", "torre", "alfil"}
MAX_MAP_ROWS = 100
MAX_MAP_COLUMNS = 100
MAX_MAP_CELLS = 10_000
MAX_UNITS = 200
MAX_KINGS = 200
MAX_ADVERSARIAL_DEPTH = 5


class ScenarioValidationError(ValueError):
    """Error que agrupa las infracciones del contrato o del estado inicial."""

    def __init__(self, errors: list[str]):
        """Guarda los errores y construye un mensaje legible para registro o API."""
        self.errors = errors
        super().__init__("; ".join(errors))


def _is_integer(value: Any) -> TypeGuard[int]:
    """Indica si un valor es entero, excluyendo los booleanos de Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_json_values(value: Any, field: str, errors: list[str]) -> None:
    """Comprueba UTF-8 y números finitos en todo el árbol JSON."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if isinstance(key, str):
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError:
                    errors.append(f"{field}: las claves deben ser compatibles con UTF-8")
                    key_field = f"{field}[clave Unicode inválida]"
                else:
                    key_field = f"{field}.{key}"
            else:
                key_field = f"{field}[clave]"
            _check_json_values(nested_value, key_field, errors)
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            _check_json_values(nested_value, f"{field}[{index}]", errors)
    elif isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            errors.append(f"{field}: las cadenas deben ser compatibles con UTF-8")
    elif isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{field}: los números JSON deben ser finitos")


def validate_utf8_string(value: str, field: str) -> None:
    """Rechaza nombres que no pueden representarse en una respuesta UTF-8."""
    errors: list[str] = []
    _check_json_values(value, field, errors)
    if errors:
        raise ScenarioValidationError(errors)


def carrier_winner(state: dict[str, Any]) -> str | None:
    """Devuelve el bando del portador activo situado en su propia base."""
    game = state.get("juego", {})
    carrier_id = game.get("portador_recurso") if isinstance(game, dict) else None
    units = state.get("unidades", [])
    carrier = next(
        (unit for unit in units if isinstance(unit, dict) and unit.get("id") == carrier_id),
        None,
    ) if isinstance(units, list) else None
    if carrier is None or carrier.get("activo", True) is not True:
        return None
    side = carrier.get("bando")
    base = state.get("bases", {}).get(side)
    if side in ("A", "B") and isinstance(base, dict) and (
        carrier.get("fila"), carrier.get("columna")
    ) == (base.get("fila"), base.get("columna")):
        return side
    return None


def _check_position(
    value: Any,
    field: str,
    rows: int | None,
    columns: int | None,
    terrain: Any,
    terrain_types: Any,
    errors: list[str],
) -> tuple[int, int] | None:
    """Valida coordenadas, límites y transitabilidad; devuelve la posición si existe."""
    if not isinstance(value, dict):
        errors.append(f"{field}: debe ser un objeto con fila y columna")
        return None

    row = value.get("fila")
    column = value.get("columna")
    if not _is_integer(row) or not _is_integer(column):
        errors.append(f"{field}: fila y columna deben ser enteros")
        return None

    if rows is None or columns is None:
        return row, column
    if not (0 <= row < rows and 0 <= column < columns):
        errors.append(f"{field}: posición ({row}, {column}) fuera del mapa")
        return row, column

    if isinstance(terrain, list) and row < len(terrain) and isinstance(terrain[row], list) and column < len(terrain[row]):
        terrain_id = terrain[row][column]
        definition = (
            terrain_types.get(terrain_id)
            if isinstance(terrain_types, dict) and isinstance(terrain_id, str)
            else None
        )
        if isinstance(definition, dict) and definition.get("transitable") is False:
            errors.append(f"{field}: la posición ({row}, {column}) está sobre un obstáculo")
    return row, column


def _check_terrain(scenario: dict[str, Any], errors: list[str]) -> tuple[int | None, int | None]:
    """Valida dimensiones, catálogo y matriz; devuelve las dimensiones válidas."""
    map_data = scenario.get("mapa")
    rows = columns = None
    if not isinstance(map_data, dict):
        errors.append("mapa: debe ser un objeto")
    else:
        rows_value = map_data.get("filas")
        columns_value = map_data.get("columnas")
        if not _is_integer(rows_value) or rows_value <= 0:
            errors.append("mapa.filas: debe ser un entero positivo")
        elif rows_value > MAX_MAP_ROWS:
            errors.append(f"mapa.filas: no puede exceder {MAX_MAP_ROWS}")
        else:
            rows = rows_value
        if not _is_integer(columns_value) or columns_value <= 0:
            errors.append("mapa.columnas: debe ser un entero positivo")
        elif columns_value > MAX_MAP_COLUMNS:
            errors.append(f"mapa.columnas: no puede exceder {MAX_MAP_COLUMNS}")
        else:
            columns = columns_value
        if (
            _is_integer(rows_value)
            and _is_integer(columns_value)
            and rows_value > 0
            and columns_value > 0
            and rows_value * columns_value > MAX_MAP_CELLS
        ):
            errors.append(f"mapa: no puede exceder {MAX_MAP_CELLS} celdas")

    terrain_types = scenario.get("tipos_terreno")
    if not isinstance(terrain_types, dict):
        errors.append("tipos_terreno: debe ser un objeto")
        terrain_types = {}
    else:
        for terrain_id, definition in terrain_types.items():
            field = f"tipos_terreno.{terrain_id}"
            if not isinstance(definition, dict):
                errors.append(f"{field}: debe ser un objeto")
                continue
            walkable = definition.get("transitable")
            if not isinstance(walkable, bool):
                errors.append(f"{field}.transitable: debe ser booleano")
            if walkable is True:
                cost = definition.get("costo")
                if (
                    not isinstance(cost, (int, float))
                    or isinstance(cost, bool)
                    or (isinstance(cost, float) and not math.isfinite(cost))
                    or cost <= 0
                ):
                    errors.append(f"{field}.costo: debe ser un número positivo para terreno transitable")

    terrain = scenario.get("terreno")
    if not isinstance(terrain, list):
        errors.append("terreno: debe ser una matriz")
    else:
        if rows is not None and len(terrain) != rows:
            errors.append(f"terreno: declara {len(terrain)} filas, pero mapa.filas indica {rows}")
        for row_index, row in enumerate(terrain):
            if not isinstance(row, list):
                errors.append(f"terreno[{row_index}]: debe ser una fila de la matriz")
                continue
            if columns is not None and len(row) != columns:
                errors.append(
                    f"terreno[{row_index}]: declara {len(row)} columnas, pero mapa.columnas indica {columns}"
                )
            for column_index, terrain_id in enumerate(row):
                if not isinstance(terrain_id, str) or terrain_id not in terrain_types:
                    errors.append(f"terreno[{row_index}][{column_index}]: tipo de terreno desconocido {terrain_id!r}")

    return rows, columns


def validate_scenario(scenario: dict[str, Any]) -> None:
    """Valida el contrato JSON y acumula los errores que puede detectar.

    Recorre el árbol JSON, el mapa, las unidades, los reyes y los terrenos:
    tiempo O(N + R*C + U + K + T), espacio auxiliar O(U + K + E).
    No modifica el escenario ni usa IA; las búsquedas pueden confiar en sus invariantes.
    

    Purpose: Rechazar escenarios externos que incumplan el contrato del profesor.
    Preconditions: JSON externo suministrado.
    Postconditions: Acepta o falla sin mutar un juego ya cargado.
    Complexity: O(F*C+U+K) más comprobaciones de conectividad.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    if not isinstance(scenario, dict):
        raise ScenarioValidationError(["escenario: debe ser un objeto JSON"])

    errors: list[str] = []
    _check_json_values(scenario, "$", errors)
    required_fields = ("version", "mapa", "tipos_terreno", "terreno", "bases", "recurso", "unidades", "turno", "juego")
    for field in required_fields:
        if field not in scenario:
            errors.append(f"{field}: campo obligatorio ausente")

    version = scenario.get("version")
    if "version" in scenario and (not isinstance(version, str) or not version.strip()):
        errors.append("version: debe ser una cadena no vacía")
    if scenario.get("turno") not in ("A", "B"):
        errors.append("turno: debe ser 'A' o 'B'")

    rows, columns = _check_terrain(scenario, errors)
    terrain = scenario.get("terreno")
    terrain_types = scenario.get("tipos_terreno")

    base_positions: dict[str, tuple[int, int]] = {}
    bases = scenario.get("bases")
    if not isinstance(bases, dict):
        errors.append("bases: debe ser un objeto")
    else:
        for side in ("A", "B"):
            if side not in bases:
                errors.append(f"bases.{side}: campo obligatorio ausente")
                continue
            position = _check_position(
                bases[side], f"bases.{side}", rows, columns, terrain, terrain_types, errors
            )
            if position is not None:
                base_positions[side] = position

    units = scenario.get("unidades")
    unit_by_id: dict[str, dict[str, Any]] = {}
    active_positions: dict[tuple[int, int], str] = {}
    if not isinstance(units, list):
        errors.append("unidades: debe ser una lista")
        units = []
    elif len(units) > MAX_UNITS:
        errors.append(f"unidades: no puede contener más de {MAX_UNITS} elementos")
    for index, unit in enumerate(units):
        field = f"unidades[{index}]"
        if not isinstance(unit, dict):
            errors.append(f"{field}: debe ser un objeto")
            continue
        for name in ("id", "bando", "tipo", "fila", "columna"):
            if name not in unit:
                errors.append(f"{field}.{name}: campo obligatorio ausente")

        unit_id = unit.get("id")
        if not isinstance(unit_id, str) or not unit_id.strip():
            errors.append(f"{field}.id: debe ser una cadena no vacía")
        elif unit_id in unit_by_id:
            errors.append(f"{field}.id: identificador repetido {unit_id!r}")
        else:
            unit_by_id[unit_id] = unit

        if unit.get("bando") not in ("A", "B"):
            errors.append(f"{field}.bando: debe ser 'A' o 'B'")
        unit_type = unit.get("tipo")
        if not isinstance(unit_type, str) or unit_type not in SUPPORTED_UNIT_TYPES:
            errors.append(f"{field}.tipo: tipo de unidad desconocido {unit_type!r}")

        if "activo" in unit and not isinstance(unit["activo"], bool):
            errors.append(f"{field}.activo: debe ser booleano")
        position = _check_position(
            {"fila": unit.get("fila"), "columna": unit.get("columna")},
            field,
            rows,
            columns,
            terrain,
            terrain_types,
            errors,
        )
        if position is not None and unit.get("activo", True) is True:
            if position in active_positions:
                errors.append(
                    f"{field}: se superpone con la unidad activa {active_positions[position]!r}"
                )
            else:
                active_positions[position] = unit_id if isinstance(unit_id, str) else field

    game = scenario.get("juego")
    carrier_id: str | None = None
    if not isinstance(game, dict):
        errors.append("juego: debe ser un objeto")
    elif "portador_recurso" not in game:
        errors.append("juego.portador_recurso: campo obligatorio ausente")
    else:
        carrier = game["portador_recurso"]
        if carrier is not None and (not isinstance(carrier, str) or not carrier.strip()):
            errors.append("juego.portador_recurso: debe ser un identificador o null")
        elif isinstance(carrier, str):
            carrier_id = carrier
            if carrier_id not in unit_by_id:
                errors.append(f"juego.portador_recurso: unidad inexistente {carrier_id!r}")
            elif unit_by_id[carrier_id].get("activo", True) is not True:
                errors.append("juego.portador_recurso: la unidad portadora debe estar activa")
        if "estado" in game and game["estado"] not in ("configuracion", "en_curso", "finalizado"):
            errors.append("juego.estado: valor desconocido")
        if "resultado" in game and game["resultado"] not in (None, "A", "B", "empate"):
            errors.append("juego.resultado: debe ser null, 'A', 'B' o 'empate'")
        configured_depth = game.get("profundidad_maxima_minimax", 3)
        if type(configured_depth) is not int or configured_depth < 0:
            errors.append(
                "juego.profundidad_maxima_minimax: debe ser un entero mayor o igual a 0"
            )

    resource = scenario.get("recurso")
    resource_position: tuple[int, int] | None = None
    if resource is None:
        if carrier_id is None:
            errors.append("recurso: debe tener una posición cuando no existe portador")
    else:
        resource_position = _check_position(
            resource, "recurso", rows, columns, terrain, terrain_types, errors
        )

    if carrier_id is not None:
        carrier_unit = unit_by_id.get(carrier_id)
        if carrier_unit is not None and resource_position is not None:
            carrier_position = (carrier_unit.get("fila"), carrier_unit.get("columna"))
            if carrier_position != resource_position:
                errors.append("recurso: debe ser null o coincidir con la posición de la unidad portadora")

    resource_spawn = scenario.get("recurso_spawn")
    resource_spawn_position: tuple[int, int] | None = None
    if resource_spawn is not None:
        resource_spawn_position = _check_position(
            resource_spawn,
            "recurso_spawn",
            rows,
            columns,
            terrain,
            terrain_types,
            errors,
        )
    elif carrier_id is not None and resource is None:
        errors.append(
            "recurso_spawn: debe conservar el spawn original cuando la reina ya tiene portador"
        )
    if (
        carrier_id is None
        and resource_position is not None
        and resource_spawn_position is not None
        and resource_spawn_position != resource_position
    ):
        errors.append("recurso_spawn: debe coincidir con la posición inicial de recurso")

    kings: list[tuple[str, tuple[int, int]]] = []
    king_ids: set[str] = set()
    if "reyes" in scenario:
        king_groups = scenario["reyes"]
        if not isinstance(king_groups, dict):
            errors.append("reyes: debe ser un objeto por bando")
        else:
            for side in king_groups:
                if side not in ("A", "B"):
                    errors.append(f"reyes.{side}: bando desconocido; debe ser 'A' o 'B'")
            for side in ("A", "B"):
                group = king_groups.get(side, [])
                if not isinstance(group, list):
                    errors.append(f"reyes.{side}: debe ser una lista")
                    continue
                if len(group) > MAX_KINGS:
                    errors.append(
                        f"reyes.{side}: no puede contener más de {MAX_KINGS} elementos"
                    )
                for index, king in enumerate(group):
                    field = f"reyes.{side}[{index}]"
                    if not isinstance(king, dict):
                        errors.append(f"{field}: debe ser un objeto")
                        continue
                    king_id = king.get("id")
                    if king_id is not None:
                        if not isinstance(king_id, str) or not king_id.strip():
                            errors.append(f"{field}.id: debe ser una cadena no vacía")
                        elif king_id in king_ids:
                            errors.append(f"{field}.id: identificador de rey repetido {king_id!r}")
                        else:
                            king_ids.add(king_id)
                    position = _check_position(
                        king, field, rows, columns, terrain, terrain_types, errors
                    )
                    if position is None:
                        continue
                    kings.append((field, position))
                    if position in active_positions:
                        errors.append(f"{field}: se superpone con la unidad {active_positions[position]!r}")
                    if position in base_positions.values():
                        errors.append(f"{field}: un rey no puede ocupar una base")
                    if carrier_id is None and position == resource_position:
                        errors.append(f"{field}: un rey no puede ocupar la posición del recurso")
                    if carrier_id is not None and position == resource_spawn_position:
                        errors.append(f"{field}: un rey no puede ocupar recurso_spawn")

            seen_king_positions: set[tuple[int, int]] = set()
            for field, position in kings:
                if position in seen_king_positions:
                    errors.append(f"{field}: se superpone con otro rey")
                seen_king_positions.add(position)

    if "prueba" in scenario:
        test_config = scenario["prueba"]
        if not isinstance(test_config, dict):
            errors.append("prueba: debe ser un objeto")
        else:
            mode = test_config.get("modo")
            if mode not in ("busqueda", "partida", "adversarial"):
                errors.append("prueba.modo: debe ser 'busqueda', 'partida' o 'adversarial'")
            elif mode == "busqueda":
                unit_id = test_config.get("unidad_inicio")
                if not isinstance(unit_id, str) or unit_id not in unit_by_id:
                    errors.append(f"prueba.unidad_inicio: unidad inexistente {unit_id!r}")
                if "objetivo" not in test_config:
                    errors.append("prueba.objetivo: campo obligatorio para modo busqueda")
                else:
                    _check_position(
                        test_config["objetivo"], "prueba.objetivo", rows, columns,
                        terrain, terrain_types, errors
                    )

    if errors:
        raise ScenarioValidationError(errors)


def _base_positions_connected(state: dict[str, Any]) -> bool:
    """Comprueba conectividad ortogonal de las bases sin ocupar casillas de rey."""
    bases = state.get("bases", {})
    if not isinstance(bases, dict) or "A" not in bases or "B" not in bases:
        return False
    try:
        start = (bases["A"]["fila"], bases["A"]["columna"])
        target = (bases["B"]["fila"], bases["B"]["columna"])
    except (KeyError, TypeError):
        return False
    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]
    king_positions = {
        (king["fila"], king["columna"])
        for group in state.get("reyes", {}).values()
        if isinstance(group, list)
        for king in group
        if isinstance(king, dict)
        and type(king.get("fila")) is int
        and type(king.get("columna")) is int
    }

    def open_cell(position: tuple[int, int]) -> bool:
        row, column = position
        if not (0 <= row < rows and 0 <= column < columns) or position in king_positions:
            return False
        terrain_id = state["terreno"][row][column]
        definition = state["tipos_terreno"].get(terrain_id)
        return isinstance(definition, dict) and definition.get("transitable") is True

    if not open_cell(start) or not open_cell(target):
        return False
    reachable = {start}
    pending = [start]
    while pending:
        row, column = pending.pop()
        for neighbor in ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1)):
            if neighbor not in reachable and open_cell(neighbor):
                reachable.add(neighbor)
                pending.append(neighbor)
    return target in reachable


def validate_state(
    state: dict[str, Any], *, check_connectivity: bool = True
) -> None:
    """Valida el estado; la conectividad se puede omitir tras validar el escenario.

    `check_connectivity` debe permanecer activo al cargar/configurar reyes. Las
    transiciones pueden omitirlo porque no cambian terreno, bases ni reyes.
    Complexity: O(R*C + U + K); espacio O(R*C + U + K).
    

    Purpose: Comprobar invariantes de partida para motor y API.
    Preconditions: Estado ya cargado o candidato a transición.
    Postconditions: Acepta coherencia completa o informa errores.
    Complexity: O(F*C+U+K) y verificaciones de accesibilidad opcionales.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    if not isinstance(state, dict):
        raise ScenarioValidationError(["estado: debe ser un objeto JSON"])

    errors: list[str] = []
    units = state.get("unidades")
    if isinstance(units, list):
        scenario_units: list[dict[str, Any]] = []
        for index, unit in enumerate(units):
            if not isinstance(unit, dict):
                scenario_units.append(unit)
                continue
            scenario_unit = dict(unit)
            if unit.get("activo", True) is False:
                if (unit.get("fila"), unit.get("columna")) != (-1, -1):
                    errors.append(f"unidades[{index}]: una unidad inactiva debe estar fuera del tablero")
                spawn = unit.get("spawn")
                if isinstance(spawn, dict):
                    scenario_unit["fila"] = spawn.get("fila")
                    scenario_unit["columna"] = spawn.get("columna")
            scenario_units.append(scenario_unit)
        validation_state = dict(state)
        validation_state["unidades"] = scenario_units
    else:
        validation_state = state

    try:
        validate_scenario(validation_state)
    except ScenarioValidationError as error:
        errors.extend(error.errors)
        if errors:
            raise ScenarioValidationError(errors) from error

    game = state.get("juego")
    if not isinstance(game, dict):
        errors.append("juego: debe ser un objeto")
    else:
        status = game.get("estado")
        result = game.get("resultado")
        if status not in ("configuracion", "en_curso", "finalizado"):
            errors.append("juego.estado: debe ser 'configuracion', 'en_curso' o 'finalizado'")
        if "resultado" not in game or result not in (None, "A", "B", "empate"):
            errors.append("juego.resultado: debe ser null, 'A', 'B' o 'empate'")
        if status == "finalizado" and result is None:
            errors.append("juego.resultado: una partida finalizada requiere resultado")
        if status != "finalizado" and result is not None:
            errors.append("juego.resultado: solo puede existir en una partida finalizada")
        carrier_id = game.get("portador_recurso")
        if carrier_id is not None and state.get("recurso") is not None:
            errors.append("recurso: debe ser null mientras la reina tenga portador")
        winner = carrier_winner(state)
        if status == "finalizado" and result in ("A", "B") and winner != result:
            errors.append("juego.resultado: el ganador debe transportar la reina en su base")
        if status != "finalizado" and winner is not None:
            errors.append("juego.estado: una victoria por portador debe estar finalizada")
        if status == "finalizado" and result == "empate" and winner is not None:
            errors.append("juego.resultado: no puede haber empate con un portador en su base")

    if isinstance(units, list):
        rows = state.get("mapa", {}).get("filas")
        columns = state.get("mapa", {}).get("columnas")
        for index, unit in enumerate(units):
            if not isinstance(unit, dict):
                continue
            spawn = unit.get("spawn")
            if spawn is None:
                errors.append(f"unidades[{index}].spawn: posición inicial ausente")
                continue
            if isinstance(rows, int) and isinstance(columns, int):
                _check_position(
                    spawn,
                    f"unidades[{index}].spawn",
                    rows,
                    columns,
                    state.get("terreno"),
                    state.get("tipos_terreno"),
                    errors,
                )

    if isinstance(units, list):
        spawn_owners: dict[tuple[int, int], list[str]] = {}
        for unit in units:
            if not isinstance(unit, dict) or not isinstance(unit.get("spawn"), dict):
                continue
            spawn = unit["spawn"]
            row, column = spawn.get("fila"), spawn.get("columna")
            if type(row) is int and type(column) is int:
                spawn_owners.setdefault((row, column), []).append(str(unit.get("id", "?")))
        king_groups = state.get("reyes", {})
        if isinstance(king_groups, dict):
            for side, group in king_groups.items():
                if not isinstance(group, list):
                    continue
                for index, king in enumerate(group):
                    if not isinstance(king, dict):
                        continue
                    row, column = king.get("fila"), king.get("columna")
                    if type(row) is not int or type(column) is not int:
                        continue
                    owners = spawn_owners.get((row, column))
                    if owners:
                        errors.append(
                            f"reyes.{side}[{index}]: no puede ocupar el spawn de la unidad {owners[0]!r}"
                        )

    turn = state.get("turno")
    if (
        not errors
        and isinstance(game, dict)
        and game.get("estado") == "finalizado"
        and game.get("resultado") == "empate"
        and isinstance(turn, str)
        and turn in ("A", "B")
        and has_legal_action(state, turn)
    ):
        errors.append("juego.resultado: no puede haber empate mientras el bando en turno tenga acciones legales")

    if check_connectivity and not errors and not _base_positions_connected(state):
        errors.append("bases: los reyes no deben bloquear la conexión transitable entre las bases")
    if errors:
        raise ScenarioValidationError(errors)


def _action_position(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        row = value.get("fila", value.get("row"))
        column = value.get("columna", value.get("column"))
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        row, column = value
    else:
        raise ValueError("El destino debe incluir fila y columna")
    if type(row) is not int or type(column) is not int:
        raise ValueError("Las coordenadas del destino deben ser enteros")
    return {"fila": row, "columna": column}


def validate_action(state: dict[str, Any], action: dict[str, Any]) -> None:
    """Valida movimiento o recogida explícita sin modificar el estado.

    Preconditions: estado preparado, acción JSON y bando en turno.
    Postconditions: una acción ilegal lanza `ValueError` y una estructura/tipo
    inválido lanza `TypeError`; el movimiento consulta `move_cost`, que exige un
    destino incluido en `legal_moves`.
    Complexity: O(U + K*U*max(F,C) + D), según movimiento, jaque y trayecto.
    

    Purpose: Validar una acción completa contra el estado vigente.
    Preconditions: Estado coherente y acción solicitada.
    Postconditions: Autoriza transición legal o falla antes de modificar el estado.
    Complexity: O(U+K+F+C) según patrón y jaque.
    AI usage: Yes.
    AI intervention: apoyo de IA en diseño, revisión, documentación o pruebas; verificar el alcance preciso en el informe.
    Student validation: hay pruebas automatizadas; la comprobación y defensa personal de los integrantes sigue pendiente.
    """
    if not isinstance(action, dict):
        raise TypeError("La acción debe ser un objeto")
    kind = action.get("type", action.get("tipo", action.get("action")))
    if kind is None:
        kind = "move" if "destination" in action or "destino" in action else "collect"
    if not isinstance(kind, str):
        raise TypeError(f"El tipo de acción debe ser una cadena, no {type(kind).__name__}")
    kind = {
        "mover": "move",
        "movimiento": "move",
        "recoger": "collect",
        "recoger_reina": "collect",
        "collect_queen": "collect",
    }.get(kind, kind)
    if kind not in ("move", "collect"):
        raise ValueError(f"Acción desconocida: {kind!r}")

    game = state.get("juego")
    if not isinstance(game, dict):
        raise TypeError("El estado no contiene un objeto de partida válido")
    if game.get("estado") == "finalizado" or game.get("resultado") is not None:
        raise ValueError("La partida ha finalizado y no acepta acciones")
    if game.get("estado") not in ("configuracion", "en_curso"):
        raise ValueError("La partida no está disponible para jugar")

    unit_id = action.get("unit_id", action.get("unidad_id"))
    if not isinstance(unit_id, str) or not unit_id:
        raise ValueError("La acción debe indicar una unidad")
    unit = next((candidate for candidate in state.get("unidades", []) if candidate.get("id") == unit_id), None)
    if unit is None:
        raise ValueError(f"No existe la unidad {unit_id!r}")
    if unit.get("activo", True) is not True:
        raise ValueError(f"La unidad {unit_id!r} está inactiva")
    if unit.get("bando") != state.get("turno"):
        raise ValueError(f"La unidad {unit_id!r} no pertenece al bando en turno")

    if kind == "move":
        destination = _action_position(action.get("destination", action.get("destino")))
        try:
            move_cost(state, unit_id, destination)
        except ValueError as error:
            raise ValueError(
                f"El destino {destination} no es legal para la unidad {unit_id!r}"
            ) from error
        return

    if game.get("portador_recurso") is not None or not isinstance(state.get("recurso"), dict):
        raise ValueError("La reina no está disponible para recoger")
    queen = _action_position(state["recurso"])
    if (unit.get("fila"), unit.get("columna")) != (queen["fila"], queen["columna"]):
        raise ValueError("La unidad debe estar sobre la casilla de la reina para recogerla")
    if is_in_check(state, unit["bando"]):
        raise ValueError("No se puede recoger la reina mientras el propio rey está en jaque")