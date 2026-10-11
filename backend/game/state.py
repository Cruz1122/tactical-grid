def state_key(state: dict) -> tuple:
    raise NotImplementedError

def successors(state: dict) -> list[dict]:
    raise NotImplementedError

def is_goal(state: dict, goal: dict) -> bool:
    raise NotImplementedError

def transition(state: dict, action: dict) -> dict:
    raise NotImplementedError
