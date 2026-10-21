from typing import Any

from backend.game.movement import move_cost
from backend.game.movement import terrain_cost as _terrain_cost


def terrain_cost(
    state: dict[str, Any], position: dict[str, int] | tuple[int, int] | int, column: int | None = None
) -> float:
    """Mantener la firma de compatibilidad para lectura de costos de terreno.
    
    Purpose: Mantener la firma de compatibilidad para lectura de costos de terreno.
    Preconditions: Estado con catálogo; coordenadas en dict/tupla o fila y columna.
    Postconditions: Costo real delegado al módulo movement, sin mutaciones.
    Complexity: O(1) por acceso a celda y catálogo.
    AI usage: Yes.
    AI intervention: IA asistió revisión de compatibilidad del contrato y mensajes de error.
    Student validation: Pruebas de costos y de parámetros; revisión personal pendiente.
    """
    if column is not None:
        if not isinstance(position, int) or isinstance(position, bool):
            raise TypeError("La fila debe ser un entero")
        return _terrain_cost(state, (position, column))
    if isinstance(position, int):
        raise TypeError("La posición debe incluir fila y columna")
    return _terrain_cost(state, position)


__all__ = ["move_cost", "terrain_cost"]