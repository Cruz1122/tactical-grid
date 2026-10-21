"""Reproduce una autopartida verificable sin alterar los criterios terminales del motor."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from time import perf_counter

from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.minimax import minimax
from backend.game.engine import check_winner, state_key, transition
from backend.scenarios import prepare_scenario


def play_game(path: Path, algorithm: str, depth: int, max_turns: int, repetition_limit: int = 3) -> dict:
    """Evalúa turnos completos y registra un diagnóstico reproducible.

    Purpose: medir si una política adversarial llega a estado terminal o se atasca.
    Preconditions: archivo JSON válido y límites enteros positivos.
    Postconditions: traza de acciones legales y causa de interrupción experimental;
    una repetición NO se declara empate oficial del juego.
    Complexity: O(T*b^d*C), donde T turnos, b ramificación y C transición/evaluación.
    AI usage: Yes.
    AI intervention: diseño del banco reproducible y el diagnóstico de ciclos.
    Student validation: ejecutar y comprobar personalmente antes de la sustentación.
    """
    source = json.loads(path.read_text(encoding="utf-8"))
    state = prepare_scenario(deepcopy(source))
    search = alpha_beta if algorithm == "alpha_beta" else minimax
    seen = {state_key(state): 1}
    trace = []
    start = perf_counter()
    reason = "max_turns"
    for number in range(1, max_turns + 1):
        if check_winner(state) is not None:
            reason = "terminal"
            break
        result = search(state, depth)
        action = result["action"]
        if action is None:
            reason = "without_action"
            break
        side = state["turno"]
        candidate = transition(state, action)
        trace.append({
            "turn": number,
            "side": side,
            "action": action,
            "value": result["value"],
            "nodes_visited": result["nodes_visited"],
            "elapsed_seconds": result["elapsed_seconds"],
            "queen_carrier_after": candidate["juego"].get("portador_recurso"),
            "queen_after": candidate.get("recurso"),
            "winner_after": check_winner(candidate),
        })
        state = candidate
        if check_winner(state) is not None:
            reason = "terminal"
            break
        key = state_key(state)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= repetition_limit:
            reason = "repetition_detected"
            break
    return {
        "scenario": path.name,
        "algorithm": algorithm,
        "depth": depth,
        "turns": len(trace),
        "stop_reason": reason,
        "winner": check_winner(state),
        "elapsed_seconds": perf_counter() - start,
        "total_nodes": sum(item["nodes_visited"] for item in trace),
        "trace": trace,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce una partida desde un escenario JSON")
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--algorithm", choices=("minimax", "alpha_beta"), default="alpha_beta")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-turns", type=int, default=150)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.depth < 1 or arguments.max_turns < 1:
        parser.error("depth y max-turns deben ser positivos")
    result = play_game(arguments.scenario, arguments.algorithm, arguments.depth, arguments.max_turns)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "trace"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()