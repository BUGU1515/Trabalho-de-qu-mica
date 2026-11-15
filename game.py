import asyncio
import copy
import math
import random

from js import document, window
from pyodide.ffi import create_proxy


canvas = document.getElementById("gameCanvas")
ctx = canvas.getContext("2d")
question_el = document.getElementById("question")
level_el = document.getElementById("level")

CELL_SIZE = 44
WALL_SIZE = 14
GRID_W = 25
GRID_H = 15
canvas.width = GRID_W * CELL_SIZE + WALL_SIZE
canvas.height = GRID_H * CELL_SIZE + WALL_SIZE

questions = [
    {
        "question": "Qual a unidade de energia no Sistema Internacional?",
        "answers": ["JOULE", "CALORIA", "WATT", "ERG"],
        "correct": 0,
    },
    {
        "question": "Como é chamada a reação química que absorve calor?",
        "answers": ["ENDOTÉRMICA", "EXOTÉRMICA", "ISOTÉRMICA", "ADIABÁTICA"],
        "correct": 0,
    },
    {
        "question": "O que a Entalpia mede em uma reação química?",
        "answers": ["CALOR TROCADO", "TEMPERATURA", "PRESSÃO", "VOLUME"],
        "correct": 0,
    },
    {
        "question": "O que a Lei de Hess afirma sobre a variação de entalpia?",
        "answers": [
            "INDEPENDE DO CAMINHO",
            "DEPENDE DA PRESSÃO",
            "VARIA COM TEMPERATURA",
            "É SEMPRE POSITIVA",
        ],
        "correct": 0,
    },
    {
        "question": "O que o calor precisa para mudar de fase?",
        "answers": ["CALOR LATENTE", "CALOR SENSÍVEL", "CALOR ESPECÍFICO", "CAPACIDADE TÉRMICA"],
        "correct": 0,
    },
]

player = {"x": 100, "y": 100, "width": 30, "height": 36, "speed": 8.5}
state = {
    "phase": 0,
    "active": False,
    "transition": False,
    "message": "",
    "message_until": 0,
    "time_left": 50,
    "timer_id": None,
    "maze": None,
    "maze_cache": {},
    "door": {"x": 0, "y": 0, "width": 72, "height": 78},
    "door_open": False,
    "key_obtained": False,
    "key": {"x": 0, "y": 0, "active": False},
    "key_cells_used": {},
    "key_corners_used": set(),
    "plate_cells_used": set(),
    "answer_collected": False,
    "door_unlocked": False,
    "answers": [],
    "walls": [],
    "free_cells": [],
    "start": {"x": 0, "y": 0},
    "victory": False,
    "finished": False,
    "victory_button": {"x": 0, "y": 0, "w": 200, "h": 60},
    "preparation": False,
    "keys": set(),
    "animation_id": None,
    "plates": [],
    "plate_timeout_ms": 10000,
    "lives": 2,
    "reset_pending": False,
}
images = {
    "robot": document.getElementById("robotImage"),
    "door": document.getElementById("doorImage"),
    "open_door": document.getElementById("openDoorImage"),
    "key": document.getElementById("keyImage"),
    "plate": document.getElementById("plateImage"),
    "pressed_plate": document.getElementById("pressedPlateImage"),
    "full_heart": document.getElementById("fullHeartImage"),
    "empty_heart": document.getElementById("emptyHeartImage"),
}


def cell_to_pixel(col, row):
    return {"x": WALL_SIZE + col * CELL_SIZE, "y": WALL_SIZE + row * CELL_SIZE}


def create_preparation_room():
    maze_w, maze_h = 13, 9
    maze_width = maze_w * CELL_SIZE + WALL_SIZE
    maze_height = maze_h * CELL_SIZE + WALL_SIZE
    maze_x = (canvas.width - maze_width) / 2
    maze_y = (canvas.height - maze_height) / 2
    grid = [[True] * maze_w for _ in range(maze_h)]
    grid[1][1] = False
    stack = [(1, 1)]
    directions = ((2, 0), (-2, 0), (0, 2), (0, -2))
    while stack:
        col, row = stack[-1]
        neighbors = [
            (col + dc, row + dr, col + dc // 2, row + dr // 2)
            for dc, dr in directions
            if 0 < col + dc < maze_w - 1
            and 0 < row + dr < maze_h - 1
            and grid[row + dr][col + dc]
        ]
        if not neighbors:
            stack.pop()
            continue
        next_col, next_row, wall_col, wall_row = random.choice(neighbors)
        grid[next_row][next_col] = False
        grid[wall_row][wall_col] = False
        stack.append((next_col, next_row))

    free_cells = [
        {"col": col, "row": row}
        for row in range(maze_h)
        for col in range(maze_w)
        if not grid[row][col]
    ]
    start = {"col": 1, "row": 1}
    door_cell = max(
        free_cells,
        key=lambda cell: abs(cell["col"] - start["col"]) + abs(cell["row"] - start["row"]),
    )
    walls = [
        [0, 0, canvas.width, WALL_SIZE],
        [0, canvas.height - WALL_SIZE, canvas.width, WALL_SIZE],
        [0, 0, WALL_SIZE, canvas.height],
        [canvas.width - WALL_SIZE, 0, WALL_SIZE, canvas.height],
        [maze_x, maze_y, maze_width, WALL_SIZE],
        [maze_x, maze_y + maze_height - WALL_SIZE, maze_width, WALL_SIZE],
        [maze_x, maze_y, WALL_SIZE, maze_height],
        [maze_x + maze_width - WALL_SIZE, maze_y, WALL_SIZE, maze_height],
    ]
    for row in range(maze_h):
        for col in range(maze_w):
            if grid[row][col]:
                walls.append(
                    [
                        maze_x + WALL_SIZE + col * CELL_SIZE,
                        maze_y + WALL_SIZE + row * CELL_SIZE,
                        CELL_SIZE,
                        CELL_SIZE,
                    ]
                )
    door_width, door_height = 82, 78
    door_x = maze_x + WALL_SIZE + door_cell["col"] * CELL_SIZE
    door_y = maze_y + WALL_SIZE + door_cell["row"] * CELL_SIZE
    start_x = maze_x + WALL_SIZE + start["col"] * CELL_SIZE
    start_y = maze_y + WALL_SIZE + start["row"] * CELL_SIZE
    return {
        "walls": walls,
        "player_x": start_x + (CELL_SIZE - player["width"]) / 2,
        "player_y": start_y + (CELL_SIZE - player["height"]) / 2,
        "door": {
            "x": door_x + (CELL_SIZE - door_width) / 2,
            "y": door_y,
            "width": door_width,
            "height": door_height,
        },
    }


def generate_maze():
    grid = [[True] * GRID_W for _ in range(GRID_H)]
    start_col = 1 + 2 * random.randrange(math.ceil((GRID_W - 2) / 2))
    start_row = 1 + 2 * random.randrange(math.ceil((GRID_H - 2) / 2))
    grid[start_row][start_col] = False
    stack = [(start_col, start_row)]
    directions = [(2, 0), (-2, 0), (0, 2), (0, -2)]

    while stack:
        col, row = stack[-1]
        neighbors = [
            (col + dc, row + dr, col + dc // 2, row + dr // 2)
            for dc, dr in directions
            if 0 < col + dc < GRID_W - 1
            and 0 < row + dr < GRID_H - 1
            and grid[row + dr][col + dc]
        ]
        if not neighbors:
            stack.pop()
            continue
        next_col, next_row, wall_col, wall_row = random.choice(neighbors)
        grid[next_row][next_col] = False
        grid[wall_row][wall_col] = False
        stack.append((next_col, next_row))

    walls = [
        [0, 0, canvas.width, WALL_SIZE],
        [0, canvas.height - WALL_SIZE, canvas.width, WALL_SIZE],
        [0, 0, WALL_SIZE, canvas.height],
        [canvas.width - WALL_SIZE, 0, WALL_SIZE, canvas.height],
    ]
    free_cells = []
    for row in range(GRID_H):
        for col in range(GRID_W):
            if grid[row][col]:
                walls.append(
                    [WALL_SIZE + col * CELL_SIZE, WALL_SIZE + row * CELL_SIZE, CELL_SIZE, CELL_SIZE]
                )
            else:
                free_cells.append({"col": col, "row": row})

    start_cell, door_cell = free_cells[0], free_cells[-1]
    start_pixel = cell_to_pixel(start_cell["col"], start_cell["row"])
    door_pixel = cell_to_pixel(door_cell["col"], door_cell["row"])
    player_x = start_pixel["x"] + (CELL_SIZE - player["width"]) / 2
    player_y = start_pixel["y"] + (CELL_SIZE - player["height"]) / 2

    return {
        "walls": walls,
        "door_pixel": door_pixel,
        "player_x": player_x,
        "player_y": player_y,
        "free_cells": free_cells,
        "grid": grid,
        "start_cell": start_cell,
        "door_cell": door_cell,
    }


def get_cached_maze(phase):
    if phase not in state["maze_cache"]:
        state["maze_cache"][phase] = generate_maze()
    return copy.deepcopy(state["maze_cache"][phase])


def show_objective(message, duration):
    state["message"] = ""
    state["message_until"] = 0


def find_cell_path(start, goal, free_cells):
    free = {(cell["col"], cell["row"]) for cell in free_cells}
    queue = [(start, [start])]
    visited = set()
    while queue:
        current, path = queue.pop(0)
        key = (current["col"], current["row"])
        if key in visited:
            continue
        visited.add(key)
        if key == (goal["col"], goal["row"]):
            return path
        for dc, dr in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            neighbor = (key[0] + dc, key[1] + dr)
            if neighbor in free and neighbor not in visited:
                cell = {"col": neighbor[0], "row": neighbor[1]}
                queue.append((cell, path + [cell]))
    return [start, goal]


def position_answers_in_dead_ends(free_cells, start, goal):
    if len(free_cells) < 4:
        return []
    path_cells = {
        (cell["col"], cell["row"]) for cell in find_cell_path(start, goal, free_cells)
    }
    free = {(cell["col"], cell["row"]) for cell in free_cells}
    safe_cells = [
        cell for cell in free_cells
        if 2 <= cell["col"] <= GRID_W - 3 and 2 <= cell["row"] <= GRID_H - 3
    ]
    dead_ends = []
    for cell in safe_cells:
        key = (cell["col"], cell["row"])
        neighbors = sum(
            (key[0] + dc, key[1] + dr) in free
            for dc, dr in ((0, -1), (0, 1), (-1, 0), (1, 0))
        )
        if key not in path_cells and neighbors == 1:
            dead_ends.append(cell)
    if len(dead_ends) < 4:
        dead_ends = [
            cell for cell in safe_cells if (cell["col"], cell["row"]) not in path_cells
        ]
    if len(dead_ends) < 4:
        dead_ends = [
            cell for cell in free_cells if (cell["col"], cell["row"]) not in path_cells
        ]

    best_selection = None
    best_min_distance = 0
    for _ in range(50):
        if len(dead_ends) < 4:
            break
        selected = random.sample(dead_ends, 4)
        min_distance = min(
            abs(a["col"] - b["col"]) + abs(a["row"] - b["row"])
            for index, a in enumerate(selected)
            for b in selected[index + 1 :]
        )
        if min_distance > best_min_distance:
            best_min_distance = min_distance
            best_selection = selected
        if min_distance >= 7:
            break
    selected = best_selection or dead_ends[:4]
    return [
        {
            "x": WALL_SIZE + cell["col"] * CELL_SIZE + CELL_SIZE / 2,
            "y": WALL_SIZE + cell["row"] * CELL_SIZE + CELL_SIZE / 2,
            "col": cell["col"],
            "row": cell["row"],
        }
        for cell in selected
    ]


def collides_with_wall(x, y, width, height):
    return any(
        x < wall[0] + wall[2]
        and x + width > wall[0]
        and y < wall[1] + wall[3]
        and y + height > wall[1]
        for wall in state["walls"]
    )


def answer_at_player():
    center_x = player["x"] + player["width"] / 2
    center_y = player["y"] + player["height"] / 2
    return next(
        (
            answer
            for answer in state["answers"]
            if answer["x"] - 68 < center_x < answer["x"] + 68
            and answer["y"] - 24 < center_y < answer["y"] + 24
        ),
        None,
    )


def at_door():
    center_x = player["x"] + player["width"] / 2
    center_y = player["y"] + player["height"] / 2
    door = state["door"]
    return math.hypot(
        center_x - door["x"] - door["width"] / 2,
        center_y - door["y"] - door["height"] / 2,
    ) < 55


def collect_key():
    key = state["key"]
    if not key["active"]:
        return False
    center_x = player["x"] + player["width"] / 2
    center_y = player["y"] + player["height"] / 2
    if math.hypot(center_x - key["x"] - 12, center_y - key["y"] - 12) < 20:
        key["active"] = False
        return True
    return False


def show_feedback(text, color):
    element = document.createElement("div")
    element.className = "feedback"
    element.textContent = text
    element.style.color = color
    document.body.appendChild(element)

    def remove_feedback():
        element.remove()
        feedback_proxy.destroy()

    feedback_proxy = create_proxy(remove_feedback)
    window.setTimeout(feedback_proxy, 800)


def update_hearts():
    for index in range(2):
        heart = document.getElementById(f"heart{index}")
        is_full = index < state["lives"]
        heart.src = images["full_heart"].src if is_full else images["empty_heart"].src
        heart.alt = "Coração cheio" if is_full else "Coração vazio"


def lose_life():
    if state["reset_pending"] or state["lives"] <= 0:
        return
    heart_index = state["lives"] - 1
    heart = document.getElementById(f"heart{heart_index}")
    heart.src = images["empty_heart"].src
    heart.alt = "Coração vazio"
    heart.classList.remove("heart-damage")
    state["lives"] -= 1

    def begin_heart_animation(_timestamp=None):
        heart.classList.add("heart-damage")
        animation_proxy.destroy()

        def clear_heart_animation():
            heart.classList.remove("heart-damage")
            removal_proxy.destroy()

        removal_proxy = create_proxy(clear_heart_animation)
        window.setTimeout(removal_proxy, 450)

    animation_proxy = create_proxy(begin_heart_animation)
    window.requestAnimationFrame(animation_proxy)
    if state["lives"] == 0:
        state["reset_pending"] = True
        if state["timer_id"] is not None:
            window.clearInterval(state["timer_id"])
            state["timer_id"] = None
        asyncio.create_task(return_to_preparation())


def update_timer_ui():
    timer = document.getElementById("timer")
    timer.style.display = "flex"
    text = f"⏱️ {state['time_left']}s"
    plate_deadlines = [
        plate["active_until"] for plate in state["plates"] if plate["active_until"]
    ]
    if plate_deadlines:
        plate_seconds = math.ceil(max(0, min(plate_deadlines) - window.Date.now()) / 1000)
        text += f" | Placas: {plate_seconds}s"
    timer.textContent = text
    if state["time_left"] <= 10:
        timer.classList.add("timer-warning")
    else:
        timer.classList.remove("timer-warning")


def time_expired():
    if not state["active"] or state["victory"] or state["reset_pending"]:
        return
    lose_life()
    if state["reset_pending"]:
        return
    player["x"], player["y"] = state["start"]["x"], state["start"]["y"]
    state["answer_collected"] = False
    state["door_unlocked"] = False
    state["key_obtained"] = False
    state["door_open"] = False
    for answer in state["answers"]:
        answer["status"] = "pending"
        answer["pressed_at"] = 0
    configure_phase_objects(state["maze"])
    start_timer()


def timer_tick():
    if not state["active"] or state["transition"] or state["victory"]:
        return
    state["time_left"] -= 1
    update_timer_ui()
    if state["time_left"] <= 0:
        if state["timer_id"] is not None:
            window.clearInterval(state["timer_id"])
            state["timer_id"] = None
        time_expired()


timer_tick_proxy = create_proxy(timer_tick)


def start_timer():
    if state["timer_id"] is not None:
        window.clearInterval(state["timer_id"])
    state["time_left"] = 35 if state["phase"] == 5 else 50
    document.querySelector(".hearts-box").style.display = "flex"
    update_timer_ui()
    state["timer_id"] = window.setInterval(timer_tick_proxy, 1000)


def configure_phase_objects(maze):
    if state["phase"] not in (2, 4, 5):
        state["key"] = {"x": 0, "y": 0, "active": False}
    else:
        start, door = maze["start_cell"], maze["door_cell"]
        answer_cells = {(answer["col"], answer["row"]) for answer in state["answers"]}
        phase = state["phase"]
        previous = state["key_cells_used"].setdefault(phase, set())
        key_candidates = [
            cell for cell in maze["free_cells"]
            if (cell["col"], cell["row"]) not in answer_cells
            and (cell["col"], cell["row"]) not in previous
            and (cell["col"], cell["row"]) != (start["col"], start["row"])
            and (cell["col"], cell["row"]) != (door["col"], door["row"])
        ]
        if not key_candidates:
            previous.clear()
            key_candidates = [
                cell for cell in maze["free_cells"]
                if (cell["col"], cell["row"]) not in answer_cells
                and (cell["col"], cell["row"]) != (start["col"], start["row"])
                and (cell["col"], cell["row"]) != (door["col"], door["row"])
            ]
        if len(key_candidates) == 0:
            raise RuntimeError(f"Não há células livres para a chave da fase {state['phase']}.")
        used_corners = state["key_corners_used"]
        mid_col, mid_row = GRID_W // 2, GRID_H // 2
        corner_cells = {
            0: lambda cell: cell["col"] <= mid_col and cell["row"] <= mid_row,
            1: lambda cell: cell["col"] > mid_col and cell["row"] <= mid_row,
            2: lambda cell: cell["col"] <= mid_col and cell["row"] > mid_row,
            3: lambda cell: cell["col"] > mid_col and cell["row"] > mid_row,
        }
        available_corners = [
            corner for corner, contains in corner_cells.items()
            if corner not in used_corners
            and any(contains(cell) for cell in key_candidates)
        ]
        if not available_corners:
            used_corners.clear()
            available_corners = [
                corner for corner, contains in corner_cells.items()
                if any(contains(cell) for cell in key_candidates)
            ]
        corner = random.choice(available_corners)
        used_corners.add(corner)
        in_corner = [cell for cell in key_candidates if corner_cells[corner](cell)]
        corner_distance = {
            0: lambda cell: cell["col"] + cell["row"],
            1: lambda cell: GRID_W - 1 - cell["col"] + cell["row"],
            2: lambda cell: cell["col"] + GRID_H - 1 - cell["row"],
            3: lambda cell: GRID_W - 1 - cell["col"] + GRID_H - 1 - cell["row"],
        }[corner]
        in_corner.sort(key=corner_distance)
        selected = random.choice(in_corner[: max(1, len(in_corner) // 4)])
        previous.add((selected["col"], selected["row"]))
        state["key_cells_used"][state["phase"]] = previous
        state["key"] = {
            "x": WALL_SIZE + selected["col"] * CELL_SIZE + (CELL_SIZE - 30) / 2,
            "y": WALL_SIZE + selected["row"] * CELL_SIZE + (CELL_SIZE - 30) / 2,
            "active": False,
        }
        state["key_obtained"] = False

    state["plates"] = []
    if state["phase"] in (3, 5):
        answer_cells = {
            (answer["col"], answer["row"])
            for answer in state["answers"]
        }
        key_cell = None
        if state["phase"] == 5:
            key_cell = (
                round((state["key"]["x"] - WALL_SIZE) / CELL_SIZE),
                round((state["key"]["y"] - WALL_SIZE) / CELL_SIZE),
            )
        door_cell = (maze["door_cell"]["col"], maze["door_cell"]["row"])
        start_cell = (maze["start_cell"]["col"], maze["start_cell"]["row"])
        start = maze["start_cell"]
        candidates = [
            cell
            for cell in maze["free_cells"]
            if (cell["col"], cell["row"]) not in answer_cells
            and (cell["col"], cell["row"]) != key_cell
            and (cell["col"], cell["row"]) != door_cell
            and (cell["col"], cell["row"]) != start_cell
            and abs(cell["col"] - start["col"]) + abs(cell["row"] - start["row"]) >= 3
        ]
        if len(candidates) < 2:
            candidates = [
                cell
                for cell in maze["free_cells"]
                if (cell["col"], cell["row"]) not in answer_cells
                and (cell["col"], cell["row"]) != key_cell
                and (cell["col"], cell["row"]) != door_cell
                and (cell["col"], cell["row"]) != start_cell
            ]
        previously_used = state["plate_cells_used"]
        fresh_candidates = [
            cell for cell in candidates
            if (cell["col"], cell["row"]) not in previously_used
        ]
        if len(fresh_candidates) >= 2:
            candidates = fresh_candidates
        else:
            previously_used.clear()
        if len(candidates) < 2:
            raise RuntimeError(f"Não há células livres suficientes para as placas da fase {state['phase']}.")
        first = random.choice(candidates)
        second = max(
            (cell for cell in candidates if cell is not first),
            key=lambda cell: abs(cell["col"] - first["col"]) + abs(cell["row"] - first["row"]),
        )
        for cell in (first, second):
            previously_used.add((cell["col"], cell["row"]))
            state["plates"].append(
                {
                    "x": WALL_SIZE + cell["col"] * CELL_SIZE + CELL_SIZE / 2,
                    "y": WALL_SIZE + cell["row"] * CELL_SIZE + CELL_SIZE / 2,
                    "active_until": 0,
                    "touching": False,
                }
            )


def create_victory_phase():
    walls = [
        [0, 0, canvas.width, WALL_SIZE],
        [0, canvas.height - WALL_SIZE, canvas.width, WALL_SIZE],
        [0, 0, WALL_SIZE, canvas.height],
        [canvas.width - WALL_SIZE, 0, WALL_SIZE, canvas.height],
    ]
    button = {"x": (canvas.width - 200) / 2, "y": canvas.height / 2 + 30, "w": 200, "h": 60}
    state["victory_button"] = button
    return {"walls": walls, "player_x": 60, "player_y": canvas.height - 100}


def remove_timer():
    timer = document.getElementById("timer")
    if timer:
        timer.style.display = "none"


def restart_quiz(*_args):
    if state["transition"]:
        return
    asyncio.create_task(restart_with_transition())


async def fade_transition():
    overlay = document.createElement("div")
    overlay.className = "fade-transition"
    document.body.appendChild(overlay)
    await asyncio.sleep(0.05)
    overlay.classList.add("active")
    await asyncio.sleep(0.5)
    return overlay


async def return_to_preparation():
    overlay = await fade_transition()
    state["maze_cache"] = {}
    state["key_cells_used"] = {}
    state["key_corners_used"] = set()
    state["plate_cells_used"] = set()
    state["phase"] = 0
    state["victory"] = False
    state["finished"] = False
    state["transition"] = False
    state["reset_pending"] = False
    state["lives"] = 2
    state["key_obtained"] = False
    state["answer_collected"] = False
    state["door_unlocked"] = False
    state["door_open"] = True
    state["plates"] = []
    update_hearts()
    document.getElementById("victoryScreen").hidden = True
    document.getElementById("startScreen").hidden = True
    document.getElementById("instructionsScreen").hidden = True
    overlay.remove()
    iniciar_jogo()


async def restart_with_transition():
    if state["transition"]:
        return
    state["transition"] = True
    if state["timer_id"] is not None:
        window.clearInterval(state["timer_id"])
        state["timer_id"] = None
    overlay = await fade_transition()
    overlay.remove()
    state["maze_cache"] = {}
    state["key_cells_used"] = {}
    state["key_corners_used"] = set()
    state["plate_cells_used"] = set()
    state["phase"] = 0
    state["victory"] = False
    state["finished"] = False
    state["transition"] = False
    state["reset_pending"] = False
    state["lives"] = 2
    update_hearts()
    document.getElementById("victoryScreen").hidden = True
    document.getElementById("startScreen").hidden = True
    document.getElementById("instructionsScreen").hidden = True
    iniciar_jogo()


async def advance_phase():
    if state["transition"] or state["victory"] or state["finished"] or state["reset_pending"]:
        return
    state["transition"] = True
    if state["timer_id"] is not None:
        window.clearInterval(state["timer_id"])
        state["timer_id"] = None

    overlay = await fade_transition()
    overlay.remove()

    state["phase"] = 1 if state["phase"] == 0 else state["phase"] + 1
    if state["phase"] > 5:
        state["victory"] = True
        state["finished"] = True
        victory = create_victory_phase()
        state["walls"] = victory["walls"]
        player["x"], player["y"] = victory["player_x"], victory["player_y"]
        state["start"] = {"x": player["x"], "y": player["y"]}
        question_el.textContent = "🏆 VITÓRIA! 🏆"
        level_el.textContent = "Fim de jogo"
        remove_timer()
        document.getElementById("victoryScreen").hidden = False
        state["transition"] = False
        return

    maze = get_cached_maze(state["phase"])
    state["maze"] = maze
    state["walls"] = maze["walls"]
    state["free_cells"] = maze["free_cells"]
    state["start"] = {"x": maze["player_x"], "y": maze["player_y"]}
    player["x"], player["y"] = maze["player_x"], maze["player_y"]
    door_pixel = maze["door_pixel"]
    door_x = door_pixel["x"] + (CELL_SIZE - 76) / 2
    door_y = door_pixel["y"] + (CELL_SIZE - 71) / 2
    state["door"] = {"x": door_x, "y": door_y, "width": 76, "height": 71}
    state["door_open"] = False

    answer_positions = position_answers_in_dead_ends(
        maze["free_cells"], maze["start_cell"], maze["door_cell"]
    )
    shuffled_answers = questions[state["phase"] - 1]["answers"][:]
    random.shuffle(shuffled_answers)
    correct_answer = questions[state["phase"] - 1]["answers"][
        questions[state["phase"] - 1]["correct"]
    ]
    state["answers"] = [
        {
            "x": answer_positions[index]["x"],
            "y": answer_positions[index]["y"],
            "col": answer_positions[index]["col"],
            "row": answer_positions[index]["row"],
            "text": answer,
            "correct": answer == correct_answer,
            "status": "pending",
            "pressed_at": 0,
        }
        for index, answer in enumerate(shuffled_answers)
    ]

    configure_phase_objects(maze)
    state["answer_collected"] = False
    state["door_unlocked"] = False
    question_el.textContent = questions[state["phase"] - 1]["question"]
    level_el.textContent = f"Fase {state['phase']}/5"
    start_timer()
    state["transition"] = False


def draw_rounded_rect(x, y, width, height, radius):
    radius = min(radius, width / 2, height / 2)
    ctx.beginPath()
    ctx.moveTo(x + radius, y)
    ctx.lineTo(x + width - radius, y)
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
    ctx.lineTo(x + width, y + height - radius)
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height)
    ctx.lineTo(x + radius, y + height)
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius)
    ctx.lineTo(x, y + radius)
    ctx.quadraticCurveTo(x, y, x + radius, y)
    ctx.closePath()


def draw_map():
    ctx.fillStyle = "#0a0a2a"
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    for _ in range(150):
        ctx.fillStyle = f"rgba(255,255,255,{random.random() * 0.4})"
        ctx.fillRect(random.random() * canvas.width, random.random() * canvas.height, 2, 2)


def draw_walls():
    for wall in state["walls"]:
        ctx.fillStyle = "#4a6a3a"
        ctx.fillRect(*wall)
        ctx.fillStyle = "#2a4a1a"
        ctx.fillRect(wall[0] + 2, wall[1] + 2, wall[2] - 4, wall[3] - 4)
        ctx.strokeStyle = "#ffd700"
        ctx.lineWidth = 1.5
        ctx.strokeRect(wall[0] + 1, wall[1] + 1, wall[2] - 2, wall[3] - 2)


def draw_player():
    image = images["robot"]
    if image.complete and image.naturalWidth:
        ctx.drawImage(image, player["x"] - 5, player["y"] - 2, 40, 40)
        return
    ctx.save()
    ctx.shadowBlur = 12
    ctx.shadowColor = "#00aaff"
    ctx.fillStyle = "#ffffff"
    ctx.beginPath()
    ctx.ellipse(player["x"] + 11, player["y"] + 13, 9, 14, 0, 0, math.pi * 2)
    ctx.fill()
    ctx.fillStyle = "#2277ff"
    ctx.beginPath()
    ctx.arc(player["x"] + 5, player["y"] + 6, 5, 0, math.pi * 2)
    ctx.arc(player["x"] + 17, player["y"] + 6, 5, 0, math.pi * 2)
    ctx.fill()
    ctx.fillStyle = "#fff"
    ctx.beginPath()
    ctx.arc(player["x"] + 5, player["y"] + 6, 2, 0, math.pi * 2)
    ctx.arc(player["x"] + 17, player["y"] + 6, 2, 0, math.pi * 2)
    ctx.fill()
    ctx.fillStyle = "#555"
    ctx.fillRect(player["x"] + 7, player["y"] + 21, 8, 12)
    ctx.restore()


def draw_answers():
    now = window.Date.now()
    for answer in state["answers"]:
        status = answer["status"]
        if status == "removed":
            continue
        if status in ("wrong", "dismissed"):
            progress = (now - answer["pressed_at"]) / 260
            if progress >= 1:
                answer["status"] = "removed"
                continue
            scale = 1 + progress * 0.75
            alpha = 1 - progress
        else:
            scale = 1
            alpha = 1
        width, height = 136 * scale, 48 * scale
        ctx.save()
        ctx.globalAlpha = alpha
        ctx.shadowBlur = 6
        ctx.shadowColor = "#0088ff"
        ctx.fillStyle = "#238b45" if status == "correct" else (
            "#bf3030" if status == "wrong" else "#1e5faa"
        )
        draw_rounded_rect(answer["x"] - width / 2, answer["y"] - height / 2, width, height, 8 * scale)
        ctx.fill()
        ctx.strokeStyle = "#88ff9a" if status == "correct" else (
            "#ff9090" if status == "wrong" else "#44aaff"
        )
        ctx.lineWidth = 2
        draw_rounded_rect(answer["x"] - width / 2, answer["y"] - height / 2, width, height, 8 * scale)
        ctx.stroke()
        ctx.fillStyle = "#fff"
        ctx.font = "bold 13px Arial, sans-serif"
        ctx.textAlign = "center"
        ctx.textBaseline = "middle"
        lines = []
        current_line = ""
        for word in answer["text"].split():
            candidate = f"{current_line} {word}".strip()
            if current_line and len(candidate) > 13:
                lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line:
            lines.append(current_line)
        for index, line in enumerate(lines):
            line_y = answer["y"] + (index - (len(lines) - 1) / 2) * 14
            ctx.fillText(line, answer["x"], line_y, width - 14)
        ctx.restore()


def draw_door():
    door = state["door"]
    image = images["open_door"] if state["door_open"] else images["door"]
    if image.complete and image.naturalWidth:
        ctx.drawImage(image, door["x"], door["y"], door["width"], door["height"])
        return
    ctx.fillStyle = "#8B5A2B"
    ctx.fillRect(door["x"], door["y"], door["width"], door["height"])
    ctx.fillStyle = "#D2B48C"
    ctx.fillRect(door["x"] + 6, door["y"] + 6, door["width"] - 12, door["height"] - 12)
    ctx.fillStyle = "#FFD700"
    ctx.fillRect(door["x"] + 18, door["y"] + 25, 12, 24)


def draw_key():
    key = state["key"]
    if not key["active"]:
        return
    image = images["key"]
    if image.complete and image.naturalWidth:
        ctx.drawImage(image, key["x"], key["y"], 30, 30)
        return
    ctx.fillStyle = "#FFD700"
    ctx.beginPath()
    ctx.arc(key["x"] + 12, key["y"] + 12, 9, 0, math.pi * 2)
    ctx.fill()
    ctx.fillStyle = "#B8860B"
    ctx.fillRect(key["x"] + 9, key["y"] + 1, 6, 10)
    ctx.fillStyle = "#FFF"
    ctx.font = "bold 12px Arial"
    ctx.textAlign = "center"
    ctx.fillText("🔑", key["x"] + 12, key["y"] + 13)


def draw_objective():
    if window.Date.now() >= state["message_until"]:
        return
    ctx.font = 'bold 20px "Courier New"'
    ctx.fillStyle = "#FFD700"
    ctx.shadowBlur = 10
    ctx.shadowColor = "#000"
    ctx.textAlign = "center"
    ctx.fillText(state["message"], canvas.width / 2, 45)


def plates_required():
    return state["phase"] in (3, 5)


def plates_available():
    if not state["answer_collected"]:
        return False
    return state["phase"] != 5 or state["key_obtained"]


def update_plates():
    now = window.Date.now()
    expired = False
    for plate in state["plates"]:
        if plate["active_until"] and plate["active_until"] <= now:
            plate["active_until"] = 0
            show_objective("⏱️ Uma placa desativou! Ative-a novamente.", 2500)
            expired = True
    if expired:
        update_timer_ui()

    if not plates_available():
        return
    center_x = player["x"] + player["width"] / 2
    center_y = player["y"] + player["height"] / 2
    for plate in state["plates"]:
        touching = math.hypot(center_x - plate["x"], center_y - plate["y"]) < 22
        if touching and not plate["touching"] and not plate["active_until"]:
            plate["active_until"] = now + state["plate_timeout_ms"]
            active_plates = [item for item in state["plates"] if item["active_until"]]
            if len(active_plates) == 2:
                for active_plate in active_plates:
                    active_plate["active_until"] = now + state["plate_timeout_ms"]
                show_objective("✅ Duas placas ativadas! Corra para a porta!", 3000)
            else:
                show_objective("⏱️ Placa ativada! Pise na outra em até 10 segundos!", 3000)
            update_timer_ui()
        plate["touching"] = touching


def draw_plates():
    for plate in state["plates"]:
        image = images["pressed_plate"] if plate["active_until"] else images["plate"]
        if image.complete and image.naturalWidth:
            ctx.drawImage(image, plate["x"] - 18, plate["y"] - 14, 36, 28)
        else:
            ctx.fillStyle = "#00ff88" if plate["active_until"] else "#d89132"
            draw_rounded_rect(plate["x"] - 16, plate["y"] - 12, 32, 24, 4)
            ctx.fill()


def all_plates_active():
    return bool(state["plates"]) and all(
        plate["active_until"] > window.Date.now() for plate in state["plates"]
    )


def draw_victory_phase():
    button = state["victory_button"]
    ctx.save()
    ctx.shadowBlur = 20
    ctx.shadowColor = "#FFD700"
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.font = 'bold 64px "Courier New"'
    ctx.fillStyle = "#FFD700"
    ctx.fillText("🏆 VITÓRIA! 🏆", canvas.width / 2, canvas.height / 2 - 80)
    ctx.restore()
    ctx.font = '24px "Courier New"'
    ctx.fillStyle = "#FFF"
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.fillText("Parabéns! Você completou todas as fases!", canvas.width / 2, canvas.height / 2 - 20)
    ctx.save()
    ctx.shadowBlur = 10
    ctx.shadowColor = "#00ff00"
    ctx.fillStyle = "#2a7a2a"
    draw_rounded_rect(button["x"], button["y"], button["w"], button["h"], 12)
    ctx.fill()
    ctx.strokeStyle = "#00ff00"
    ctx.lineWidth = 3
    draw_rounded_rect(button["x"], button["y"], button["w"], button["h"], 12)
    ctx.stroke()
    ctx.fillStyle = "#FFF"
    ctx.font = 'bold 28px "Courier New"'
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.fillText(
        "🔄 REINICIAR",
        button["x"] + button["w"] / 2,
        button["y"] + button["h"] / 2,
    )
    ctx.restore()
    ctx.font = '16px "Courier New"'
    ctx.fillStyle = "#AAA"
    ctx.textAlign = "center"
    ctx.fillText(
        "Ande até o botão para reiniciar o jogo",
        canvas.width / 2,
        button["y"] + button["h"] + 40,
    )


def move_player():
    dx = dy = 0
    keys = state["keys"]
    if any(key in keys for key in ("ArrowUp", "w", "W")):
        dy -= player["speed"]
    if any(key in keys for key in ("ArrowDown", "s", "S")):
        dy += player["speed"]
    if any(key in keys for key in ("ArrowLeft", "a", "A")):
        dx -= player["speed"]
    if any(key in keys for key in ("ArrowRight", "d", "D")):
        dx += player["speed"]
    if not collides_with_wall(player["x"] + dx, player["y"], player["width"], player["height"]):
        player["x"] += dx
    if not collides_with_wall(player["x"], player["y"] + dy, player["width"], player["height"]):
        player["y"] += dy
    player["x"] = max(10, min(canvas.width - player["width"] - 10, player["x"]))
    player["y"] = max(10, min(canvas.height - player["height"] - 10, player["y"]))


def handle_phase_logic():
    answer = answer_at_player()
    if answer and answer["status"] == "pending" and not state["answer_collected"]:
        if answer["correct"]:
            state["answer_collected"] = True
            answer["status"] = "correct"
            pressed_at = window.Date.now()
            for other_answer in state["answers"]:
                if other_answer is not answer and other_answer["status"] == "pending":
                    other_answer["status"] = "dismissed"
                    other_answer["pressed_at"] = pressed_at
            if state["phase"] in (2, 4, 5):
                state["key"]["active"] = True
                show_objective("", 0)
            elif state["phase"] not in (3,):
                state["door_unlocked"] = True
            answer["pressed_at"] = window.Date.now()
            show_feedback("✓ CORRETO!", "#00ff00")
        else:
            answer["status"] = "wrong"
            answer["pressed_at"] = window.Date.now()
            show_feedback("✗ RESPOSTA ERRADA!", "#ff0000")
            lose_life()
            if state["reset_pending"]:
                return

    if (
        state["phase"] in (2, 4, 5)
        and state["answer_collected"]
        and not state["key_obtained"]
        and collect_key()
    ):
        state["key_obtained"] = True
        if state["phase"] != 5:
            state["door_unlocked"] = True

    update_plates()
    if state["phase"] in (3, 5):
        can_pass = all_plates_active()
    elif state["phase"] in (2, 4):
        can_pass = state["door_unlocked"] and state["key_obtained"]
    else:
        can_pass = state["answer_collected"]
    state["door_open"] = can_pass
    if can_pass and at_door():
        asyncio.create_task(advance_phase())


def game_loop(_timestamp=None):
    if not state["active"]:
        return
    draw_map()
    draw_walls()
    if state["victory"]:
        return

    if state["preparation"]:
        draw_door()
        move_player()
        if at_door():
            state["preparation"] = False
            asyncio.create_task(advance_phase())
        draw_player()
        state["animation_id"] = window.requestAnimationFrame(animation_proxy)
        return

    draw_answers()
    draw_door()
    if state["phase"] in (2, 4, 5) and state["key"]["active"]:
        draw_key()
    if plates_required():
        draw_plates()
    draw_objective()
    move_player()
    if not state["transition"] and not state["reset_pending"]:
        handle_phase_logic()
    draw_player()
    state["animation_id"] = window.requestAnimationFrame(animation_proxy)


def on_key_down(event):
    key = event.key
    if key in ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "w", "W", "s", "S", "a", "A", "d", "D"):
        state["keys"].add(key)
        event.preventDefault()


def on_key_up(event):
    key = event.key
    if key in ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "w", "W", "s", "S", "a", "A", "d", "D"):
        state["keys"].discard(key)
        event.preventDefault()


def iniciar_jogo(*_args):
    document.getElementById("startScreen").style.display = "none"
    document.getElementById("instructionsScreen").hidden = True
    document.getElementById("victoryScreen").hidden = True
    remove_timer()
    state["active"] = True
    state["victory"] = False
    state["finished"] = False
    state["phase"] = 0
    state["preparation"] = True
    state["door_open"] = True
    state["reset_pending"] = False
    state["answers"] = []
    state["key"] = {"x": 0, "y": 0, "active": False}
    state["plates"] = []
    state["answer_collected"] = False
    state["key_obtained"] = False
    state["door_unlocked"] = False
    room = create_preparation_room()
    state["walls"] = room["walls"]
    player["x"], player["y"] = room["player_x"], room["player_y"]
    state["door"] = room["door"]
    question_el.textContent = "SALA DE PREPARAÇÃO"
    level_el.textContent = "Preparação"
    document.querySelector(".hearts-box").style.display = "none"
    show_objective("", 0)
    if state["animation_id"] is not None:
        window.cancelAnimationFrame(state["animation_id"])
    game_loop()


animation_proxy = create_proxy(game_loop)
keydown_proxy = create_proxy(on_key_down)
keyup_proxy = create_proxy(on_key_up)
instructions_screen = document.getElementById("instructionsScreen")
start_screen = document.getElementById("startScreen")
victory_screen = document.getElementById("victoryScreen")


def show_instructions(*_args):
    start_screen.hidden = True
    instructions_screen.hidden = False


def continue_to_game(*_args):
    instructions_screen.hidden = True
    iniciar_jogo()


start_button_proxy = create_proxy(show_instructions)
continue_button_proxy = create_proxy(continue_to_game)
restart_button_proxy = create_proxy(restart_quiz)
document.getElementById("startButton").addEventListener("click", start_button_proxy)
document.getElementById("continueButton").addEventListener("click", continue_button_proxy)
document.getElementById("restartButton").addEventListener("click", restart_button_proxy)
document.addEventListener("keydown", keydown_proxy)
document.addEventListener("keyup", keyup_proxy)
remove_timer()
update_hearts()
