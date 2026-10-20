"""Compatibilidad histórica para funciones de estado del motor."""

from backend.game.engine import is_goal, state_key, successors, transition

__all__ = ["is_goal", "state_key", "successors", "transition"]
