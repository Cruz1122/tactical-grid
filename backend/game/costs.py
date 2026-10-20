from typing import Any

from backend.game.movement import move_cost
from backend.game.movement import terrain_cost as _terrain_cost


def terrain_cost(
    state: dict[str, Any], position: dict[str, int] | tuple[int, int] | int, column: int | None = None
) -> float:
    """Consulta un costo de terreno, conservando la firma histórica opcional.

    Precondiciones: el estado contiene un mapa y catálogo de terrenos coherentes;
    `position` expresa `{fila, columna}` o una tupla, o se pasan fila y columna.
    Postcondiciones: devuelve el costo configurado para terreno transitable y no
    modifica el estado.
    Complejidad: O(1) en tiempo y espacio.

    Raises:
        TypeError: si la posición no tiene coordenadas enteras.
        ValueError: si la posición está fuera del mapa o no es transitable.
    """
    if column is not None:
        if not isinstance(position, int) or isinstance(position, bool):
            raise TypeError("La fila debe ser un entero")
        return _terrain_cost(state, (position, column))
    if isinstance(position, int):
        raise TypeError("La posición debe incluir fila y columna")
    return _terrain_cost(state, position)


__all__ = ["move_cost", "terrain_cost"]
