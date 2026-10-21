import json
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt
from starlette.datastructures import UploadFile

from backend.algorithms.alpha_beta import alpha_beta
from backend.algorithms.astar import astar
from backend.algorithms.beam import beam_search
from backend.algorithms.bfs import bfs
from backend.algorithms.dfs import dfs
from backend.algorithms.minimax import minimax
from backend.algorithms.ucs import ucs
from backend.algorithms.verification import verify_decision, verify_path, verify_state
from backend.game.engine import (
    apply_move,
    collect_queen,
    configure_kings,
    generate_kings,
)
from backend.game.presentation import (
    build_presentation,
    legal_move_descriptors,
    state_revision,
    transition_events,
)
from backend.game.validation import ScenarioValidationError, validate_utf8_string
from backend.scenarios import prepare_scenario

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
INITIAL = ROOT / "scenarios" / "initial.json"

with INITIAL.open(encoding="utf-8") as file:
    initial_state = prepare_scenario(json.load(file))
current_state = deepcopy(initial_state)
source_name = INITIAL.name
lock = RLock()

app = FastAPI(title="TacticalGrid")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


class Position(BaseModel):
    row: StrictInt = Field(ge=0)
    column: StrictInt = Field(ge=0)

    def as_scenario_position(self):
        """Convierte la posición de la API a las claves del JSON del escenario."""
        return {"fila": self.row, "columna": self.column}



class MoveRequest(BaseModel):
    unit_id: str = Field(min_length=1)
    destination: Position
    revision: str | None = Field(default=None, min_length=1)


class CollectRequest(BaseModel):
    unit_id: str = Field(min_length=1)
    revision: str | None = Field(default=None, min_length=1)


class KingConfigurationRequest(BaseModel):
    mode: Literal["manual", "automatic", "none"]
    kings: dict[str, list[Position]] | None = None
    counts: dict[str, StrictInt] | None = None


class SearchRequest(BaseModel):
    algorithm: Literal["bfs", "dfs", "ucs", "astar", "beam"]
    unit_id: str = Field(min_length=1)
    goal: Position
    heuristic: Literal["manhattan", "second"] = "manhattan"
    k: StrictInt = Field(default=2, ge=1)


class AdversarialRequest(BaseModel):
    algorithm: Literal["minimax", "alpha_beta"]
    depth: StrictInt | None = Field(default=None, ge=0)
    action_order: Literal["normal", "reverse"] = "normal"


class VerifyRequest(BaseModel):
    kind: Literal["state", "path", "decision"]
    result: dict[str, Any] | None = None


class TestRequest(BaseModel):
    algorithm: Literal["bfs", "dfs", "ucs", "astar", "beam", "minimax", "alpha_beta"] = "bfs"
    heuristic: Literal["manhattan", "second"] = "manhattan"
    k: StrictInt = Field(default=2, ge=1)
    depth: StrictInt | None = Field(default=None, ge=0)
    action_order: Literal["normal", "reverse"] = "normal"


@app.exception_handler(NotImplementedError)
async def missing_implementation(request, error):
    """Traduce una funcionalidad pendiente a una respuesta HTTP 501."""
    return JSONResponse(status_code=501, content={"detail": "Funcionalidad no implementada"})


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    """Devuelve en español los errores de formato detectados al leer la solicitud."""
    errors = error.errors()
    error_types = {item.get("type") for item in errors}
    if "json_invalid" in error_types:
        detail = "El cuerpo de la solicitud no contiene JSON válido."
    elif "dict_type" in error_types:
        detail = "El cuerpo de la solicitud debe ser un objeto JSON."
    else:
        locations = [
            ".".join(str(part) for part in item.get("loc", ()) if part != "body")
            for item in errors
        ]
        locations = [location for location in locations if location]
        detail = "La solicitud contiene datos con formato no válido"
        if locations:
            detail += f" en: {', '.join(locations)}"
        detail += "."
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/", include_in_schema=False)
def index():
    """Entrega el documento HTML principal de la interfaz."""
    return FileResponse(FRONTEND / "index.html")


@app.get("/styles.css", include_in_schema=False)
def styles():
    """Entrega la hoja de estilos de la interfaz."""
    return FileResponse(FRONTEND / "styles.css")


@app.get("/api.js", include_in_schema=False)
def api_script():
    """Entrega el cliente JavaScript que comunica la interfaz con la API."""
    return FileResponse(FRONTEND / "api.js", media_type="text/javascript")


@app.get("/scene.js", include_in_schema=False)
def scene_script():
    """Entrega el código JavaScript que representa la escena del tablero."""
    return FileResponse(FRONTEND / "scene.js", media_type="text/javascript")


def state_response(
    state: dict[str, Any],
    *,
    source: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project a state response without adding transient UI data to the state."""
    response: dict[str, Any] = {
        "state": deepcopy(state),
        "presentation": build_presentation(
            state,
            transition_events(previous, state) if previous is not None else (),
        ),
    }
    if source is not None:
        response["source"] = source
    return response


@app.get("/api/state")
def get_state():
    """Devuelve una copia del estado oficial y el nombre del escenario cargado."""
    with lock:
        return state_response(current_state, source=source_name)


@app.get("/api/legal-moves")
def get_legal_moves(unit_id: str = Query(min_length=1)):
    """Devuelve movimientos legales y la recogida explícita de la reina.

    La lectura nunca muta la partida. Una unidad que no pertenece al turno, una
    partida terminada o una unidad inactiva recibe una respuesta vacía con una
    razón explícita para que la interfaz pueda bloquear acciones locales sin
    convertir una lectura válida en un error de mutación.
    """
    with lock:
        state = deepcopy(current_state)
        source = source_name

    unit = next(
        (
            candidate
            for candidate in state.get("unidades", [])
            if isinstance(candidate, dict) and candidate.get("id") == unit_id
        ),
        None,
    )
    if unit is None:
        raise HTTPException(status_code=404, detail=f"No existe la unidad {unit_id!r}")

    game = state.get("juego", {})
    reason: str | None = None
    allowed = True
    if isinstance(game, dict) and game.get("estado") == "finalizado":
        allowed = False
        reason = "finalizado"
    elif unit.get("activo", True) is not True:
        allowed = False
        reason = "inactiva"
    elif unit.get("bando") != state.get("turno"):
        allowed = False
        reason = "turno"

    destinations = legal_move_descriptors(state, unit_id) if allowed else []
    normal = [
        {"row": item["row"], "column": item["column"]}
        for item in destinations
        if item["kind"] == "normal"
    ]
    captures = [
        {"row": item["row"], "column": item["column"]}
        for item in destinations
        if item["kind"] == "capture"
    ]
    presentation = build_presentation(state)
    return {
        "unit_id": unit_id,
        "allowed": allowed,
        "reason": reason,
        "destinations": destinations,
        "normal": normal,
        "captures": captures,
        "collect_allowed": presentation["recogida_autorizada"].get(unit_id, False),
        "presentation": presentation,
        "source": source,
    }


@app.post(
    "/api/scenarios",
    summary="Cargar escenario JSON",
    description=(
        "Adjunta el archivo JSON en el campo `file`. Los clientes también pueden "
        "enviar el escenario directamente como `application/json`."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Archivo JSON del escenario.",
                            }
                        },
                        "required": ["file"],
                    }
                },
            },
        }
    },
)
async def load_scenario(request: Request):
    """Valida un escenario JSON o adjunto antes de sustituir el estado oficial.

    Acepta JSON directo o un archivo multipart en el campo «file» y conserva
    el formato envuelto del cliente. La validación es O(n); si falla, responde
    HTTP 422 sin modificar la partida.
    """
    global initial_state, current_state, source_name
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    candidate_source = "scenario.json"

    if content_type == "application/json":
        try:
            body = json.loads(await request.body())
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="El cuerpo de la solicitud no contiene JSON válido.",
            ) from error
    elif content_type == "multipart/form-data":
        form = await request.form()
        try:
            uploaded_file = form.get("file")
            if not isinstance(uploaded_file, UploadFile):
                raise HTTPException(
                    status_code=422,
                    detail="Adjunta el escenario como archivo en el campo «file».",
                )
            try:
                body = json.loads(await uploaded_file.read())
            except ValueError as error:
                raise HTTPException(
                    status_code=422,
                    detail="El archivo adjunto no contiene JSON válido.",
                ) from error
            candidate_source = uploaded_file.filename or candidate_source
        finally:
            await form.close()
    else:
        raise HTTPException(
            status_code=415,
            detail="El tipo de contenido debe ser application/json o multipart/form-data.",
        )

    scenario = body
    if isinstance(body, dict) and "mapa" not in body and isinstance(body.get("scenario"), dict):
        scenario = body["scenario"]
        filename = body.get("filename")
        if isinstance(filename, str) and filename:
            candidate_source = filename

    try:
        validate_utf8_string(candidate_source, "filename")
        candidate = prepare_scenario(scenario)
    except ScenarioValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors) from error

    with lock:
        response_content = {
            "ok": True,
            "message": "Escenario cargado correctamente",
            **state_response(candidate, source=candidate_source),
        }
        try:
            response = JSONResponse(content=response_content)
        except (TypeError, ValueError, UnicodeEncodeError) as error:
            raise HTTPException(
                status_code=422,
                detail="El estado del escenario no se puede serializar como JSON UTF-8.",
            ) from error

        initial_state = candidate
        current_state = deepcopy(candidate)
        source_name = candidate_source
        return response


@app.post("/api/reset")
def reset():
    """Restaura el estado oficial a la copia inicial del escenario cargado."""
    global current_state
    with lock:
        current_state = deepcopy(initial_state)
        return state_response(current_state, source=source_name)


@app.post("/api/move")
def move(body: MoveRequest):
    """Ejecuta un movimiento legal y publica el resultado solo al completarse."""
    global current_state
    with lock:
        if body.revision is not None and body.revision != state_revision(current_state):
            raise HTTPException(
                status_code=409,
                detail="El estado de la partida cambió; vuelve a consultar los destinos legales.",
            )
        previous = deepcopy(current_state)
        try:
            candidate = apply_move(current_state, body.unit_id, body.destination.as_scenario_position())
        except ScenarioValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        current_state = candidate
        return state_response(current_state, source=source_name, previous=previous)


@app.post("/api/collect")
def collect(body: CollectRequest):
    """Recoge explícitamente la reina sin desplazar a la unidad."""
    global current_state
    with lock:
        if body.revision is not None and body.revision != state_revision(current_state):
            raise HTTPException(
                status_code=409,
                detail="El estado de la partida cambió; vuelve a consultar los destinos legales.",
            )
        previous = deepcopy(current_state)
        try:
            candidate = collect_queen(current_state, body.unit_id)
        except ScenarioValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        current_state = candidate
        return state_response(current_state, source=source_name, previous=previous)


@app.post("/api/kings")
def set_kings(body: KingConfigurationRequest):
    """Configura reyes manuales, automáticos o inicia sin ellos."""
    global current_state
    with lock:
        previous = deepcopy(current_state)
        try:
            if body.mode == "manual":
                if body.kings is None or set(body.kings) != {"A", "B"}:
                    raise ValueError("El modo manual requiere posiciones para A y B")
                kings = {
                    side: [position.as_scenario_position() for position in body.kings[side]]
                    for side in ("A", "B")
                }
                candidate = configure_kings(current_state, kings)
            elif body.mode == "automatic":
                if body.counts is None:
                    raise ValueError("El modo automático requiere cantidades para A y B")
                candidate = generate_kings(current_state, body.counts)
            else:
                candidate = configure_kings(current_state, {"A": [], "B": []})
        except ScenarioValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        current_state = candidate
        return state_response(current_state, source=source_name, previous=previous)


def search_state(state: dict, body: SearchRequest):
    """Ejecuta en el estado dado el algoritmo de búsqueda de rutas solicitado."""
    goal = body.goal.as_scenario_position()
    match body.algorithm:
        case "bfs":
            return bfs(state, body.unit_id, goal)
        case "dfs":
            return dfs(state, body.unit_id, goal)
        case "ucs":
            return ucs(state, body.unit_id, goal)
        case "astar":
            return astar(state, body.unit_id, goal, body.heuristic)
        case "beam":
            return beam_search(state, body.unit_id, goal, body.k)


@app.post("/api/search")
def search(body: SearchRequest):
    """Busca una ruta sobre una copia del estado oficial sin cambiar la partida."""
    with lock:
        state = deepcopy(current_state)
    return {"result": search_state(state, body)}


def evaluate_state(state: dict, body: AdversarialRequest):
    """Recomienda una acción sin aplicarla al estado de la partida."""
    game = state.get("juego", {})
    configured_depth = game.get("profundidad_maxima_minimax", 4) if isinstance(game, dict) else 4
    depth = body.depth if body.depth is not None else configured_depth
    if type(depth) is not int or depth < 0:
        raise HTTPException(
            status_code=422,
            detail="La profundidad configurada debe ser un entero mayor o igual que cero",
        )
    if body.algorithm == "minimax":
        return minimax(state, depth, body.action_order)
    if body.algorithm == "alpha_beta":
        return alpha_beta(state, depth, body.action_order)
    raise HTTPException(status_code=422, detail="El algoritmo adversarial no es válido")


@app.post("/api/adversarial")
def adversarial(body: AdversarialRequest):
    """Calcula una decisión adversarial sobre una copia del estado oficial."""
    with lock:
        state = deepcopy(current_state)
    return {"result": evaluate_state(state, body)}


@app.post("/api/verify")
def verify(body: VerifyRequest):
    """Verifica el estado, la ruta o la decisión indicada por la solicitud."""
    with lock:
        state = deepcopy(current_state)
    if body.kind == "state":
        result = verify_state(state)
    elif body.kind == "path":
        if body.result is None:
            raise HTTPException(status_code=422, detail="Se requiere el resultado de la ruta")
        result = verify_path(state, body.result)
    else:
        if body.result is None:
            raise HTTPException(status_code=422, detail="Se requiere el resultado de la decisión")
        result = verify_decision(state, body.result)
    return {"result": result}


@app.post("/api/test")
def test(body: TestRequest):
    """Ejecuta la prueba configurada para el escenario y el algoritmo elegido."""
    with lock:
        state = deepcopy(current_state)
    config = state.get("prueba") or {}
    mode = config.get("modo")
    if mode == "partida":
        return {"mode": mode, **state_response(state, source=source_name)}
    if mode == "busqueda":
        try:
            goal = config["objetivo"]
            if body.algorithm not in ("bfs", "dfs", "ucs", "astar", "beam"):
                raise HTTPException(status_code=422, detail="Se requiere un algoritmo de búsqueda para esta prueba")
            request = SearchRequest(
                algorithm=body.algorithm, unit_id=config["unidad_inicio"],
                goal=Position(row=goal["fila"], column=goal["columna"]),
                heuristic=body.heuristic, k=body.k
            )
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="La configuración de la prueba de búsqueda no es válida") from error
        return {"mode": mode, "result": search_state(state, request)}
    if mode == "adversarial":
        if body.algorithm in ("minimax", "alpha_beta"):
            method = body.algorithm
        elif "algorithm" not in body.model_fields_set:
            method = "minimax"
        else:
            raise HTTPException(
                status_code=422,
                detail="Se requiere minimax o alpha_beta para esta prueba adversarial",
            )
        request = AdversarialRequest(algorithm=method, depth=body.depth, action_order=body.action_order)
        return {"mode": mode, "result": evaluate_state(state, request)}
    raise HTTPException(status_code=422, detail="El modo de prueba no es válido")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
