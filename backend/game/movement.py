def legal_moves(state: dict, unit_id: str) -> list[dict]:
    raise NotImplementedError

def apply_move(state: dict, unit_id: str, destination: dict) -> dict:
    raise NotImplementedError

def capture(state: dict, attacker_id: str, victim_id: str) -> dict:
    raise NotImplementedError

def respawn(state: dict) -> dict:
    raise NotImplementedError

def check_status(state: dict) -> dict:
    raise NotImplementedError

def collect_queen(state: dict, unit_id: str) -> dict:
    raise NotImplementedError

def check_winner(state: dict) -> str | None:
    raise NotImplementedError
