from copy import deepcopy
from pathlib import Path
from threading import RLock
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any, Literal

from backend.algorithms.bfs import bfs
from backend.algorithms.dfs import dfs
from backend.algorithms.ucs import ucs
from backend.algorithms.astar import astar
from backend.algorithms.beam import beam_search
from backend.algorithms.minimax import minimax
from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.verification import verify_path, verify_state, verify_decision
from backend.game.movement import apply_move
from backend.game.validation import validate_scenario

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
INITIAL = ROOT / "scenarios" / "initial.json"

with INITIAL.open(encoding="utf-8") as file:
    initial_state = json.load(file)
current_state = deepcopy(initial_state)
source_name = INITIAL.name
lock = RLock()

app = FastAPI(title="TacticalGrid")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


class Position(BaseModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)

    def as_scenario_position(self):
        return {"fila": self.row, "columna": self.column}


class ScenarioRequest(BaseModel):
    scenario: dict[str, Any]
    filename: str = "scenario.json"


class MoveRequest(BaseModel):
    unit_id: str = Field(min_length=1)
    destination: Position


class SearchRequest(BaseModel):
    algorithm: Literal["bfs", "dfs", "ucs", "astar", "beam"]
    unit_id: str = Field(min_length=1)
    goal: Position
    heuristic: Literal["manhattan", "second"] = "manhattan"
    k: int = Field(default=2, ge=1)


class AdversarialRequest(BaseModel):
    algorithm: Literal["minimax", "alpha_beta"]
    depth: int | None = Field(default=None, ge=0)
    action_order: Literal["normal", "reverse"] = "normal"


class VerifyRequest(BaseModel):
    kind: Literal["state", "path", "decision"]
    result: dict[str, Any] | None = None


class TestRequest(BaseModel):
    algorithm: Literal["bfs", "dfs", "ucs", "astar", "beam", "minimax", "alpha_beta"] = "bfs"
    heuristic: Literal["manhattan", "second"] = "manhattan"
    k: int = Field(default=2, ge=1)
    depth: int | None = Field(default=None, ge=0)
    action_order: Literal["normal", "reverse"] = "normal"


@app.exception_handler(NotImplementedError)
async def missing_implementation(request, error):
    return JSONResponse(status_code=501, content={"detail": "Not implemented"})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/styles.css", include_in_schema=False)
def styles():
    return FileResponse(FRONTEND / "styles.css")


@app.get("/api.js", include_in_schema=False)
def api_script():
    return FileResponse(FRONTEND / "api.js", media_type="text/javascript")


@app.get("/scene.js", include_in_schema=False)
def scene_script():
    return FileResponse(FRONTEND / "scene.js", media_type="text/javascript")


@app.get("/api/state")
def get_state():
    with lock:
        return {"state": deepcopy(current_state), "source": source_name}


@app.post("/api/scenarios")
def load_scenario(body: ScenarioRequest):
    global initial_state, current_state, source_name
    candidate = deepcopy(body.scenario)
    validate_scenario(candidate)
    with lock:
        initial_state = deepcopy(candidate)
        current_state = deepcopy(candidate)
        source_name = body.filename
        return {"state": deepcopy(current_state), "source": source_name}


@app.post("/api/reset")
def reset():
    global current_state
    with lock:
        current_state = deepcopy(initial_state)
        return {"state": deepcopy(current_state), "source": source_name}


@app.post("/api/move")
def move(body: MoveRequest):
    global current_state
    with lock:
        candidate = apply_move(deepcopy(current_state), body.unit_id, body.destination.as_scenario_position())
        if not isinstance(candidate, dict):
            raise HTTPException(status_code=500, detail="apply_move must return a state")
        current_state = deepcopy(candidate)
        return {"state": deepcopy(current_state)}


def search_state(state: dict, body: SearchRequest):
    goal = body.goal.as_scenario_position()
    match body.algorithm:
        case "bfs": return bfs(state, body.unit_id, goal)
        case "dfs": return dfs(state, body.unit_id, goal)
        case "ucs": return ucs(state, body.unit_id, goal)
        case "astar": return astar(state, body.unit_id, goal, body.heuristic)
        case "beam": return beam_search(state, body.unit_id, goal, body.k)


@app.post("/api/search")
def search(body: SearchRequest):
    with lock:
        state = deepcopy(current_state)
    return {"result": search_state(state, body)}


def evaluate_state(state: dict, body: AdversarialRequest):
    depth = body.depth if body.depth is not None else state.get("juego", {}).get("profundidad_maxima_minimax", 4)
    if body.algorithm == "minimax":
        return minimax(state, depth, body.action_order)
    return alpha_beta(state, depth, body.action_order)


@app.post("/api/adversarial")
def adversarial(body: AdversarialRequest):
    with lock:
        state = deepcopy(current_state)
    return {"result": evaluate_state(state, body)}


@app.post("/api/verify")
def verify(body: VerifyRequest):
    with lock:
        state = deepcopy(current_state)
    if body.kind == "state":
        result = verify_state(state)
    elif body.kind == "path":
        result = verify_path(state, body.result)
    else:
        result = verify_decision(state, body.result)
    return {"result": result}


@app.post("/api/test")
def test(body: TestRequest):
    with lock:
        state = deepcopy(current_state)
    config = state.get("prueba") or {}
    mode = config.get("modo")
    if mode == "partida":
        return {"mode": mode, "state": state}
    if mode == "busqueda":
        try:
            goal = config["objetivo"]
            request = SearchRequest(
                algorithm=body.algorithm, unit_id=config["unidad_inicio"],
                goal=Position(row=goal["fila"], column=goal["columna"]),
                heuristic=body.heuristic, k=body.k
            )
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Invalid search test configuration") from error
        return {"mode": mode, "result": search_state(state, request)}
    if mode == "adversarial":
        method = body.algorithm if body.algorithm in ("minimax", "alpha_beta") else "minimax"
        request = AdversarialRequest(algorithm=method, depth=body.depth, action_order=body.action_order)
        return {"mode": mode, "result": evaluate_state(state, request)}
    raise HTTPException(status_code=422, detail="Invalid test mode")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
