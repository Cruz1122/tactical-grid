import math
from typing import Any, TypeGuard

SUPPORTED_UNIT_TYPES = {"knight", "rook", "bishop", "estandar", "caballo", "torre", "alfil"}


class ScenarioValidationError(ValueError):
    """Error que agrupa las infracciones del contrato o del estado inicial."""

    def __init__(self, errors: list[str]):
        """Guarda los errores y construye un mensaje legible para registro o API."""
        self.errors = errors
        super().__init__("; ".join(errors))


def _is_integer(value: Any) -> TypeGuard[int]:
    """Indica si un valor es entero, excluyendo los booleanos de Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_finite_json_values(value: Any, field: str, errors: list[str]) -> None:
    """Recorre los valores JSON y registra números no finitos con su ruta."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            _check_finite_json_values(nested_value, f"{field}.{key}", errors)
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            _check_finite_json_values(nested_value, f"{field}[{index}]", errors)
    elif isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{field}: los números JSON deben ser finitos")


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
        else:
            rows = rows_value
        if not _is_integer(columns_value) or columns_value <= 0:
            errors.append("mapa.columnas: debe ser un entero positivo")
        else:
            columns = columns_value

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
    """
    if not isinstance(scenario, dict):
        raise ScenarioValidationError(["escenario: debe ser un objeto JSON"])

    errors: list[str] = []
    _check_finite_json_values(scenario, "$", errors)
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


def validate_state(state: dict[str, Any]) -> None:
    """Comprueba las invariantes del escenario y el spawn de cada unidad.

    Recorre mapa, unidades, reyes y terrenos: tiempo O(R*C + U + K + T),
    espacio auxiliar O(U + K). No mueve unidades ni usa IA; verifica candidatos antes de cargarlos.
    """
    validate_scenario(state)
    rows = state["mapa"]["filas"]
    columns = state["mapa"]["columnas"]
    errors: list[str] = []
    for index, unit in enumerate(state["unidades"]):
        if "spawn" not in unit:
            errors.append(f"unidades[{index}].spawn: posición inicial ausente")
            continue
        _check_position(
            unit["spawn"],
            f"unidades[{index}].spawn",
            rows,
            columns,
            state["terreno"],
            state["tipos_terreno"],
            errors,
        )
    if errors:
        raise ScenarioValidationError(errors)


def validate_action(state: dict[str, Any], action: dict[str, Any]) -> None:
    """Indica que validar acciones sigue pendiente de la fase 2.

    Falla en O(1): no evalúa ni simula movimientos y no aprueba acciones.
    """
    raise NotImplementedError("validate_action sigue pendiente hasta la fase 2")
