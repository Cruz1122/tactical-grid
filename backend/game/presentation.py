"""Presentation projections for the HTTP and browser clients.

The game engine deliberately keeps transient UI data out of the official state.
This module derives a JSON-safe projection from an immutable state snapshot and
can compare two snapshots to report only confirmed transition events.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from backend.game.movement import is_in_check, legal_moves

Position = tuple[int, int]


def _position(value: Any) -> Position | None:
    """Return a valid scenario position or ``None`` for inactive/malformed data."""
    if not isinstance(value, dict):
        return None
    row = value.get("fila")
    column = value.get("columna")
    if type(row) is not int or type(column) is not int:
        return None
    return row, column


def _position_dict(position: Position) -> dict[str, int]:
    return {"fila": position[0], "columna": position[1]}


def _unit_by_id(state: dict[str, Any], unit_id: str) -> dict[str, Any] | None:
    return next(
        (
            unit
            for unit in state.get("unidades", [])
            if isinstance(unit, dict) and unit.get("id") == unit_id
        ),
        None,
    )


def _active_unit_position(unit: dict[str, Any] | None) -> Position | None:
    if not isinstance(unit, dict) or unit.get("activo", True) is not True:
        return None
    return _position(unit)


def can_collect_queen(state: dict[str, Any], unit_id: str) -> bool:
    """Determinar para una unidad si la recogida explícita está autorizada.
    
    Purpose: Determinar para una unidad si la recogida explícita está autorizada.
    Preconditions: Estado preparado, unidad identificada.
    Postconditions: Booleano coherente con portador/posición/jaque.
    Complexity: O(U+K) aproximadamente, según comprobación de amenazas.
    AI usage: Yes.
    AI intervention: IA intervino en integración de regla de recogida con respuesta visual.
    Student validation: Pruebas de permisos de recogida; revisión personal pendiente.
    """
    game = state.get("juego", {})
    if not isinstance(game, dict) or game.get("estado") == "finalizado":
        return False
    unit = _unit_by_id(state, unit_id)
    if unit is None or unit.get("bando") != state.get("turno"):
        return False
    unit_position = _active_unit_position(unit)
    queen_position = _position(state.get("recurso"))
    if (
        unit_position is None
        or queen_position is None
        or unit_position != queen_position
    ):
        return False
    return not is_in_check(state, unit["bando"])


def collection_authorizations(state: dict[str, Any]) -> dict[str, bool]:
    """Return explicit pickup authorization for every active unit."""
    return {
        unit["id"]: can_collect_queen(state, unit["id"])
        for unit in state.get("unidades", [])
        if isinstance(unit, dict) and isinstance(unit.get("id"), str)
    }


def _enemy_at(
    units_by_position: dict[Position, dict[str, Any]],
    position: Position,
    side: str | None,
) -> dict[str, Any] | None:
    occupant = units_by_position.get(position)
    if (
        occupant is not None
        and occupant.get("activo", True) is True
        and occupant.get("bando") != side
    ):
        return occupant
    return None


def _active_units_by_position(state: dict[str, Any]) -> dict[Position, dict[str, Any]]:
    result: dict[Position, dict[str, Any]] = {}
    for unit in state.get("unidades", []):
        position = _active_unit_position(unit)
        if position is not None:
            result[position] = unit
    return result


def legal_move_descriptors(state: dict[str, Any], unit_id: str) -> list[dict[str, Any]]:
    """Preparar destinos y etiquetas de captura/recogida que muestra el frontend.
    
    Purpose: Preparar destinos y etiquetas de captura/recogida que muestra el frontend.
    Preconditions: Unidad/turno y motor coherentes.
    Postconditions: Descriptores derivados exclusivamente de movimientos del motor.
    Complexity: O(L+U) para L destinos legales y clasificación de ocupación.
    AI usage: Yes.
    AI intervention: IA asistió integración backend-frontend de destinos y estados reales.
    Student validation: Pruebas de presentación y API; revisión humana pendiente.
    """
    unit = _unit_by_id(state, unit_id)
    if unit is None:
        return []
    occupied = _active_units_by_position(state)
    descriptors: list[dict[str, Any]] = []
    for destination in legal_moves(state, unit_id):
        position = _position(destination)
        if position is None:
            continue
        kind = (
            "capture" if _enemy_at(occupied, position, unit.get("bando")) else "normal"
        )
        descriptors.append(
            {
                "row": position[0],
                "column": position[1],
                "fila": position[0],
                "columna": position[1],
                "kind": kind,
            }
        )
    if can_collect_queen(state, unit_id):
        position = _active_unit_position(unit)
        if position is not None:
            descriptors.append(
                {
                    "row": position[0],
                    "column": position[1],
                    "fila": position[0],
                    "columna": position[1],
                    "kind": "collect",
                }
            )
    return descriptors


def _active_positions_by_id(state: dict[str, Any]) -> dict[str, Position]:
    positions: dict[str, Position] = {}
    for unit in state.get("unidades", []):
        if not isinstance(unit, dict) or not isinstance(unit.get("id"), str):
            continue
        position = _active_unit_position(unit)
        if position is not None:
            positions[unit["id"]] = position
    return positions


def transition_events(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> list[dict[str, Any]]:
    """Inferir eventos visuales a partir de dos estados consecutivos del motor.
    
    Purpose: Inferir eventos visuales a partir de dos estados consecutivos del motor.
    Preconditions: Estados previo y siguiente válidos.
    Postconditions: Eventos de presentación sin alterar reglas del juego.
    Complexity: O(U+K) más comparación de posiciones.
    AI usage: Yes.
    AI intervention: IA ayudó a implementar notificaciones visuales coherentes con acciones reales.
    Student validation: Pruebas de eventos de presentación; revisión personal pendiente.
    """
    if previous is None:
        return []

    current_units = {
        unit["id"]: unit
        for unit in current.get("unidades", [])
        if isinstance(unit, dict) and isinstance(unit.get("id"), str)
    }
    previous_positions = _active_positions_by_id(previous)
    current_positions = _active_positions_by_id(current)
    moved_ids = {
        unit_id
        for unit_id in previous_positions.keys() & current_positions.keys()
        if previous_positions[unit_id] != current_positions[unit_id]
    }
    previous_occupied = _active_units_by_position(previous)
    events: list[dict[str, Any]] = []
    captured_ids: set[str] = set()

    for attacker_id in sorted(moved_ids):
        attacker = current_units[attacker_id]
        destination = current_positions[attacker_id]
        victim = _enemy_at(previous_occupied, destination, attacker.get("bando"))
        if victim is None:
            continue
        victim_id = victim.get("id")
        if not isinstance(victim_id, str):
            continue
        captured_ids.add(victim_id)
        events.append(
            {
                "tipo": "captura",
                "atacante_id": attacker_id,
                "victima_id": victim_id,
                "posicion": _position_dict(destination),
            }
        )

    for unit_id in sorted(current_positions):
        if unit_id not in previous_positions:
            events.append(
                {
                    "tipo": "reaparicion",
                    "unidad_id": unit_id,
                    "posicion": _position_dict(current_positions[unit_id]),
                }
            )
            continue
        if (
            unit_id in captured_ids
            and current_positions[unit_id] != previous_positions[unit_id]
        ):
            events.append(
                {
                    "tipo": "reaparicion",
                    "unidad_id": unit_id,
                    "posicion": _position_dict(current_positions[unit_id]),
                }
            )

    previous_game = previous.get("juego", {})
    current_game = current.get("juego", {})
    previous_carrier = (
        previous_game.get("portador_recurso")
        if isinstance(previous_game, dict)
        else None
    )
    current_carrier = (
        current_game.get("portador_recurso") if isinstance(current_game, dict) else None
    )
    if current_carrier is not None and current_carrier != previous_carrier:
        carrier_position = current_positions.get(current_carrier)
        if carrier_position is not None:
            events.append(
                {
                    "tipo": "recogida",
                    "unidad_id": current_carrier,
                    "posicion": _position_dict(carrier_position),
                }
            )
    elif previous_carrier is not None and current_carrier is None:
        dropped_position = _position(current.get("recurso"))
        if dropped_position is not None:
            events.append(
                {
                    "tipo": "recurso_suelto",
                    "unidad_id": previous_carrier,
                    "posicion": _position_dict(dropped_position),
                }
            )

    previous_result = (
        previous_game.get("resultado") if isinstance(previous_game, dict) else None
    )
    current_result = (
        current_game.get("resultado") if isinstance(current_game, dict) else None
    )
    if current_result != previous_result and current_result is not None:
        events.append({"tipo": "resultado", "resultado": current_result})
    return events


def state_revision(state: dict[str, Any]) -> str:
    """Crear un identificador determinista de revisión para evitar aplicar acciones obsoletas.
    
    Purpose: Crear un identificador determinista de revisión para evitar aplicar acciones obsoletas.
    Preconditions: Estado serializable y preparado.
    Postconditions: Token estable mientras el estado no cambia.
    Complexity: O(S) para serialización/cálculo de clave.
    AI usage: Yes.
    AI intervention: IA contribuyó a controles de concurrencia y sincronización del frontend.
    Student validation: Pruebas de revisión stale y API; validación humana pendiente.
    """
    serialized = json.dumps(
        state,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()[:16]


def build_presentation(
    state: dict[str, Any], events: Iterable[dict[str, Any]] = ()
) -> dict[str, Any]:
    """Proyectar estado del juego en información que el frontend puede representar.
    
    Purpose: Proyectar estado del juego en información que el frontend puede representar.
    Preconditions: Estado oficial coherente y eventos opcionales ya calculados.
    Postconditions: Objeto visual derivado, sin modificar el estado del motor.
    Complexity: O(S+L) aproximado para copias y destinos procesados.
    AI usage: Yes.
    AI intervention: IA intervino en construcción de presentación y pruebas de coherencia de tablero.
    Student validation: Pruebas de presentación y escenas; revisión individual pendiente.
    """
    game = state.get("juego", {})
    return {
        "revision": state_revision(state),
        "jaques": {
            "A": is_in_check(state, "A"),
            "B": is_in_check(state, "B"),
        },
        "recogida_autorizada": collection_authorizations(state),
        "eventos_ultimo_turno": list(events),
        "estado": game.get("estado") if isinstance(game, dict) else None,
        "resultado": game.get("resultado") if isinstance(game, dict) else None,
        "turno": state.get("turno"),
    }


__all__ = [
    "build_presentation",
    "can_collect_queen",
    "collection_authorizations",
    "legal_move_descriptors",
    "state_revision",
    "transition_events",
]