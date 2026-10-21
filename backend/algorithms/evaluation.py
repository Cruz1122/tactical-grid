"""Valoración estratégica de estados de TacticalGrid para Minimax y alfa-beta."""

from __future__ import annotations

from collections import deque
from functools import lru_cache
from typing import Any

from backend.algorithms.adversarial_common import WIN_SCORE
from backend.game.engine import check_winner
from backend.game.movement import is_in_check, legal_moves

QUEEN_POSSESSION_SCORE = 1_000
BASE_PROXIMITY_SCORE = 200
QUEEN_PROXIMITY_SCORE = 100
ACTIVE_UNIT_SCORE = 60
CHECK_SCORE = 80
SAFE_CARRIER_SCORE = 150
THREATENED_CARRIER_SCORE = -150
# La distancia topológica guía a la pieza alrededor de obstáculos, sin calcular rutas oficiales.
QUEEN_MOVE_SCORE = 35
BASE_MOVE_SCORE = 45
INTERCEPT_MOVE_SCORE = 25
SUPPORT_MOVE_SCORES = (12, 5)
SUPPORT_INTERCEPT_SCORES = (8, 3)

_MOVES = {
    "estandar": ((1, 0), (-1, 0), (0, 1), (0, -1)),
    "knight": ((2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)),
    "rook": ((1, 0), (-1, 0), (0, 1), (0, -1)),
    "bishop": ((1, 1), (1, -1), (-1, 1), (-1, -1)),
}


def _position(value: Any) -> tuple[int, int] | None:
    """Extrae coordenadas validadas sin depender del tamaño del tablero."""
    if not isinstance(value, dict):
        return None
    row = value.get("fila", value.get("row"))
    column = value.get("columna", value.get("column"))
    return (row, column) if type(row) is int and type(column) is int else None


def _largest_map_distance(state: dict[str, Any]) -> int:
    """Devuelve el diámetro Manhattan máximo de la matriz del escenario."""
    board = state["mapa"]
    return max(0, board["filas"] - 1) + max(0, board["columnas"] - 1)


def _proximity_score(
    position: tuple[int, int], target: tuple[int, int], state: dict[str, Any], maximum: float
) -> float:
    """Conserva un pequeño factor geométrico para desempates entre distancias iguales."""
    diameter = _largest_map_distance(state)
    distance = abs(position[0] - target[0]) + abs(position[1] - target[1])
    return maximum * max(0.0, 1.0 - distance / diameter) if diameter else maximum


@lru_cache(maxsize=128)
def _distance_map(
    terrain: tuple[tuple[bool, ...], ...],
    target: tuple[int, int],
    unit_type: str,
) -> dict[tuple[int, int], int]:
    """Calcular movimientos optimistas desde un objetivo sobre bloqueos estáticos para valorar posiciones.
    
    Purpose: Calcular movimientos optimistas desde un objetivo sobre bloqueos estáticos para valorar posiciones.
    Preconditions: Matriz booleana no vacía y destino dentro de ella.
    Postconditions: Mapa de distancias mínimas según geometría básica y obstáculos; ignora turnos del adversario.
    Complexity: O(V*(F+C)) peor caso para deslizantes; O(V) para estándar/caballo; O(V) memoria, con caché.
    AI usage: Yes.
    AI intervention: IA generó la búsqueda topológica como sustitución de cercanía Manhattan después de observar oscilaciones.
    Student validation: Pruebas de rodeos y autopartida 6x6; se observó aún repetición 20x20. Revisión individual pendiente.
    """
    rows, columns = len(terrain), len(terrain[0])
    if not (0 <= target[0] < rows and 0 <= target[1] < columns and terrain[target[0]][target[1]]):
        return {}
    distances = {target: 0}
    queue = deque([target])
    sliding = unit_type in ("rook", "bishop")
    directions = _MOVES.get(unit_type, _MOVES["estandar"])
    while queue:
        row, column = queue.popleft()
        for dr, dc in directions:
            nr, nc = row + dr, column + dc
            while 0 <= nr < rows and 0 <= nc < columns and terrain[nr][nc]:
                neighbor = (nr, nc)
                if neighbor not in distances:
                    distances[neighbor] = distances[row, column] + 1
                    queue.append(neighbor)
                if not sliding:
                    break
                nr, nc = nr + dr, nc + dc
    return distances


def _movement_distance(
    state: dict[str, Any], unit: dict[str, Any], target: tuple[int, int], *, block_allies: bool = False
) -> int:
    """Traducir distancias topológicas a una unidad, opcionalmente bloqueando aliados.
    
    Purpose: Traducir distancias topológicas a una unidad, opcionalmente bloqueando aliados.
    Preconditions: Estado con mapa y unidades preparados; objetivo en coordenadas del tablero.
    Postconditions: Devuelve estimación optimista o penalización para destino inalcanzable.
    Complexity: O(F*C + U + K) para construir ocupación y mapa, más cálculo del mapa en caché; memoria O(F*C).
    AI usage: Yes.
    AI intervention: IA ayudó a integrar obstáculos, reyes y bloqueo propio en la evaluación posicional.
    Student validation: Regresión de portador bloqueado por aliados; revisión personal pendiente.
    """
    position = _position(unit)
    if position is None:
        return _largest_map_distance(state) * 2 + 1
    kings = {
        (king["fila"], king["columna"])
        for group in state.get("reyes", {}).values()
        for king in group
    }
    allies = {
        (other["fila"], other["columna"])
        for other in state["unidades"]
        if block_allies
        and other.get("activo", True) is True
        and other["bando"] == unit["bando"]
        and other["id"] != unit["id"]
    }
    terrain = tuple(
        tuple(
            (r, c) not in kings and (r, c) not in allies
            and state["tipos_terreno"][terrain_id]["transitable"]
            for c, terrain_id in enumerate(row)
        )
        for r, row in enumerate(state["terreno"])
    )
    kind = unit.get("tipo", "estandar")
    aliases = {"caballo": "knight", "torre": "rook", "alfil": "bishop"}
    kind = aliases.get(kind, kind)
    return _distance_map(terrain, target, kind).get(position, _largest_map_distance(state) * 2 + 1)


def _carrier_threatened(state: dict[str, Any], carrier: dict[str, Any]) -> bool:
    """Detectar si existe una captura legal inmediata sobre el portador del recurso.
    
    Purpose: Detectar si existe una captura legal inmediata sobre el portador del recurso.
    Preconditions: Portador activo y estado válido.
    Postconditions: Booleano sin aplicar capturas ni modificar estado.
    Complexity: O(U*L), donde L es costo de generar destinos legales por unidad enemiga.
    AI usage: Yes.
    AI intervention: IA ayudó a implementar/revisar chequeo de amenazas inmediatas para utilidad adversarial.
    Student validation: Comprobado en pruebas de decisiones y motor; validación manual del estudiante pendiente.
    """
    carrier_position = _position(carrier)
    if carrier_position is None:
        return False
    enemy_side = "B" if carrier.get("bando") == "A" else "A"
    for unit in state.get("unidades", []):
        if unit.get("activo", True) is not True or unit.get("bando") != enemy_side:
            continue
        if carrier_position in {_position(destination) for destination in legal_moves(state, unit["id"])}:
            return True
    return False


def _side_score(state: dict[str, Any], side: str) -> float:
    """Puntuar actividad, posesión, distancias, intercepción, seguridad y jaque para un bando.
    
    Purpose: Puntuar actividad, posesión, distancias, intercepción, seguridad y jaque para un bando.
    Preconditions: Estado coherente y bando A/B.
    Postconditions: Puntaje estático numérico determinado por pesos visibles del archivo.
    Complexity: Dominada por distancias topológicas y consultas a movimientos legales; depende de F*C, U y caché.
    AI usage: Yes.
    AI intervention: IA propuso e implementó pesos y factores de intercepción/soporte; se corrigieron oscilaciones detectadas.
    Student validation: Experimentos 7–10, caso 6x6 y repetición 20x20 documentada; revisión humana pendiente.
    """
    units = [u for u in state["unidades"] if u.get("activo", True) is True and u["bando"] == side]
    score = ACTIVE_UNIT_SCORE * len(units)
    carrier_id = state["juego"].get("portador_recurso")
    carrier = next((u for u in state["unidades"] if u["id"] == carrier_id), None)
    if carrier is not None and carrier["bando"] == side:
        score += QUEEN_POSSESSION_SCORE
        base = _position(state["bases"][side])
        position = _position(carrier)
        if base is not None and position is not None:
            score -= BASE_MOVE_SCORE * _movement_distance(state, carrier, base, block_allies=True)
            score += _proximity_score(position, base, state, BASE_PROXIMITY_SCORE)
        score += THREATENED_CARRIER_SCORE if _carrier_threatened(state, carrier) else SAFE_CARRIER_SCORE

    if carrier is not None and carrier["bando"] != side and units:
        # Mientras el rival transporta, las piezas propias deben intentar interceptarlo.
        target = _position(carrier)
        if target is not None:
            interception_distances = sorted(_movement_distance(state, unit, target) for unit in units)
            reach = _largest_map_distance(state) + 1
            for weight, distance in zip((INTERCEPT_MOVE_SCORE, *SUPPORT_INTERCEPT_SCORES), interception_distances):
                score += weight * max(0, reach - distance)

    queen = _position(state.get("recurso")) if carrier_id is None else None
    if queen is not None and units:
        # Solo la pieza más cercana determina el plan de recogida; las demás pueden defenderla.
        ranked = sorted(units, key=lambda u: (_movement_distance(state, u, queen), u["id"]))
        nearest = ranked[0]
        position = _position(nearest)
        reach = _largest_map_distance(state) + 1
        for weight, unit in zip((QUEEN_MOVE_SCORE, *SUPPORT_MOVE_SCORES), ranked):
            score += weight * max(0, reach - _movement_distance(state, unit, queen))
        if position is not None:
            score += _proximity_score(position, queen, state, QUEEN_PROXIMITY_SCORE)
        if is_in_check(state, "B" if side == "A" else "A"):
            score += CHECK_SCORE
    return score


def evaluate(state: dict[str, Any], side: str) -> float:
    """Devolver utilidad terminal o diferencia de puntajes para el bando fijo MAX/MIN.
    
    Purpose: Devolver utilidad terminal o diferencia de puntajes para el bando fijo MAX/MIN.
    Preconditions: Estado preparado; side es A o B.
    Postconditions: Resultado terminal ±100000/0 o diferencia simétrica; sin mutación.
    Complexity: Costo de dos evaluaciones de bando y chequeo terminal; dominado por _side_score.
    AI usage: Yes.
    AI intervention: IA participó en formulación, implementación, rediseño topológico y ajuste de pesos tras pruebas de partidas.
    Student validation: 177 tests globales aprobados y simulaciones; autoría/validación personal por método pendiente.
    """
    if side not in ("A", "B"):
        raise ValueError("El bando de evaluación debe ser 'A' o 'B'")
    winner = check_winner(state)
    if winner is not None:
        if winner == "empate":
            return 0.0
        return float(WIN_SCORE if winner == side else -WIN_SCORE)
    enemy = "B" if side == "A" else "A"
    return _side_score(state, side) - _side_score(state, enemy)