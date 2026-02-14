"""
Tetris (Solo)

Development version (loaded from badge.games.*).
For frozen/production, the same module is copied under bdg.games.*.
"""

# CRITICAL: import hardware_setup first (GUI/display init ordering)
import hardware_setup as hardware_setup  # noqa: F401

import asyncio
import random
import time

import ujson
from hardware_setup import BtnConfig, ssd

from bdg.asyncbutton import ButAct, ButtonEvents
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from gui.core.colors import (
    BLACK,
    BLUE,
    CYAN,
    GREEN,
    GREY,
    LIGHTGREEN,
    MAGENTA,
    RED,
    WHITE,
    YELLOW,
)
from gui.core.ugui import Screen, display
from gui.core.writer import CWriter
from gui.fonts import arial35, font10, freesans20
from gui.widgets import Button, Label


BOARD_W = 10
BOARD_H = 20

CELL = 8
BOARD_X = 8
BOARD_Y = 5

PANEL_X = BOARD_X + BOARD_W * CELL + 12

HISCORE_PATH = "/tetris_highscore.json"

# Input repeat tuning (ms)
DAS_MS = 160
ARR_MS = 60
POLL_MS = 20


def _shuffle_in_place(a) -> None:
    # MicroPython's random module may not implement random.shuffle().
    # Fisher-Yates shuffle using randint().
    for i in range(len(a) - 1, 0, -1):
        j = random.randint(0, i)
        a[i], a[j] = a[j], a[i]


def _ticks_ms() -> int:
    return time.ticks_ms()


def _ticks_add(t: int, delta: int) -> int:
    return time.ticks_add(t, delta)


def _ticks_diff(a: int, b: int) -> int:
    return time.ticks_diff(a, b)


# 7 tetrominoes, each defined in a 4x4 local grid.
# Each rotation is 4 (x,y) cells.
PIECES = (
    # I
    (
        ((0, 1), (1, 1), (2, 1), (3, 1)),
        ((2, 0), (2, 1), (2, 2), (2, 3)),
        ((0, 2), (1, 2), (2, 2), (3, 2)),
        ((1, 0), (1, 1), (1, 2), (1, 3)),
    ),
    # O
    (
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
    ),
    # T
    (
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (1, 2)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
    ),
    # S
    (
        ((1, 0), (2, 0), (0, 1), (1, 1)),
        ((1, 0), (1, 1), (2, 1), (2, 2)),
        ((1, 1), (2, 1), (0, 2), (1, 2)),
        ((0, 0), (0, 1), (1, 1), (1, 2)),
    ),
    # Z
    (
        ((0, 0), (1, 0), (1, 1), (2, 1)),
        ((2, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (1, 2), (2, 2)),
        ((1, 0), (0, 1), (1, 1), (0, 2)),
    ),
    # J
    (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (2, 2)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    # L
    (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (1, 2), (2, 2)),
        ((0, 1), (1, 1), (2, 1), (0, 2)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
)


# Piece colors (limited palette; 4-bit mode likely).
PIECE_COLORS = (CYAN, YELLOW, MAGENTA, GREEN, RED, BLUE, LIGHTGREEN)


class _HiScore:
    __slots__ = ("best_score", "best_lines", "best_level")

    def __init__(self, best_score=0, best_lines=0, best_level=0):
        self.best_score = int(best_score) if best_score else 0
        self.best_lines = int(best_lines) if best_lines else 0
        self.best_level = int(best_level) if best_level else 0

    @classmethod
    def load(cls):
        try:
            with open(HISCORE_PATH, "r") as f:
                d = ujson.load(f) or {}
            return cls(
                d.get("best_score", 0),
                d.get("best_lines", 0),
                d.get("best_level", 0),
            )
        except OSError:
            return cls()
        except Exception as e:
            print(f"Tetris: failed to load hiscore: {e}")
            return cls()

    def save(self):
        try:
            with open(HISCORE_PATH, "w") as f:
                ujson.dump(
                    {
                        "best_score": self.best_score,
                        "best_lines": self.best_lines,
                        "best_level": self.best_level,
                    },
                    f,
                )
        except Exception as e:
            print(f"Tetris: failed to save hiscore: {e}")


class TetrisGame:
    __slots__ = (
        "board",
        "score",
        "lines",
        "level",
        "piece_id",
        "rot",
        "px",
        "py",
        "_bag",
        "next_piece_id",
        "game_over",
    )

    def __init__(self):
        self.board = bytearray(BOARD_W * BOARD_H)  # 0 empty, else 1..7 piece color idx
        self.score = 0
        self.lines = 0
        self.level = 0

        self.piece_id = 0
        self.rot = 0
        self.px = 3  # 4x4 spawn box centered
        self.py = 0

        self._bag = []
        self.next_piece_id = self._next_from_bag()
        self.game_over = False

    def _refill_bag(self):
        self._bag = [0, 1, 2, 3, 4, 5, 6]
        _shuffle_in_place(self._bag)

    def _next_from_bag(self) -> int:
        if not self._bag:
            self._refill_bag()
        return self._bag.pop()

    def _cells_for(self, piece_id: int, rot: int, px: int, py: int):
        for dx, dy in PIECES[piece_id][rot]:
            yield px + dx, py + dy

    def _collides(self, piece_id: int, rot: int, px: int, py: int) -> bool:
        for x, y in self._cells_for(piece_id, rot, px, py):
            if x < 0 or x >= BOARD_W or y < 0 or y >= BOARD_H:
                return True
            if self.board[y * BOARD_W + x]:
                return True
        return False

    def spawn(self) -> bool:
        self.piece_id = self.next_piece_id
        self.next_piece_id = self._next_from_bag()
        self.rot = 0
        self.px = 3
        self.py = 0

        if self._collides(self.piece_id, self.rot, self.px, self.py):
            self.game_over = True
            return False
        return True

    def try_move(self, dx: int, dy: int) -> bool:
        nx = self.px + dx
        ny = self.py + dy
        if self._collides(self.piece_id, self.rot, nx, ny):
            return False
        self.px = nx
        self.py = ny
        return True

    def try_rotate_cw(self) -> bool:
        nr = (self.rot + 1) & 3
        kicks = ((0, 0), (1, 0), (-1, 0), (0, -1), (2, 0), (-2, 0))
        for kx, ky in kicks:
            nx = self.px + kx
            ny = self.py + ky
            if not self._collides(self.piece_id, nr, nx, ny):
                self.rot = nr
                self.px = nx
                self.py = ny
                return True
        return False

    def hard_drop(self) -> int:
        dropped = 0
        while self.try_move(0, 1):
            dropped += 1
        return dropped

    def lock_and_clear(self) -> int:
        color_id = self.piece_id + 1  # 1..7
        for x, y in self._cells_for(self.piece_id, self.rot, self.px, self.py):
            if 0 <= x < BOARD_W and 0 <= y < BOARD_H:
                self.board[y * BOARD_W + x] = color_id

        cleared = self._clear_lines()
        if cleared:
            self.lines += cleared
            self.level = self.lines // 10
            self.score += self._score_for_clears(cleared)
        return cleared

    def _score_for_clears(self, n: int) -> int:
        base = (0, 40, 100, 300, 1200)[n] if 0 <= n <= 4 else 0
        return base * (self.level + 1)

    def _clear_lines(self) -> int:
        cleared = 0
        write_y = BOARD_H - 1
        for read_y in range(BOARD_H - 1, -1, -1):
            full = True
            row_off = read_y * BOARD_W
            for x in range(BOARD_W):
                if self.board[row_off + x] == 0:
                    full = False
                    break
            if full:
                cleared += 1
                continue

            if write_y != read_y:
                dst_off = write_y * BOARD_W
                for x in range(BOARD_W):
                    self.board[dst_off + x] = self.board[row_off + x]
            write_y -= 1

        # Clear remaining rows at the top.
        for y in range(write_y, -1, -1):
            off = y * BOARD_W
            for x in range(BOARD_W):
                self.board[off + x] = 0

        return cleared


class TetrisGameOverScreen(Screen):
    def __init__(self, score: int, hi: _HiScore):
        super().__init__()

        wri_big = CWriter(ssd, arial35, WHITE, BLACK, verbose=False)
        wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)

        Label(wri_big, 10, 0, 320, justify=Label.CENTRE).value("GAME OVER")
        Label(wri_big, 60, 0, 320, justify=Label.CENTRE).value(str(score))

        Label(wri, 115, 0, 320, justify=Label.CENTRE).value(
            f"Best: {hi.best_score}  Lines: {hi.best_lines}  Lv: {hi.best_level}"
        )

        Button(wri, 140, 180, width=110, height=24, text="Restart", callback=self._restart)
        Button(wri, 140, 30, width=110, height=24, text="Quit", callback=self._quit)

    def _quit(self, *args):
        Screen.back()

    def _restart(self, *args):
        Screen.change(TetrisGameScreen, mode=Screen.REPLACE)


class TetrisGameScreen(Screen):
    sync_update = True

    def __init__(self):
        super().__init__()

        self._running = False
        self._paused = False

        self._game = TetrisGame()
        self._hi = _HiScore.load()

        self._task_tick = None
        self._task_btn = None

        # Cached render buffers (composite includes active piece).
        self._render_buf = bytearray(BOARD_W * BOARD_H)
        self._last_draw = bytearray(BOARD_W * BOARD_H)
        for i in range(len(self._last_draw)):
            self._last_draw[i] = 0

        self._last_score = -1
        self._last_lines = -1
        self._last_level = -1
        self._last_next_piece = -1

        self.wri_title = CWriter(ssd, freesans20, GREEN, BLACK, verbose=False)
        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)

        # Keep an active (invisible) widget so micro-gui has focus, but we handle inputs ourselves.
        HiddenActiveWidget(self.wri)

        Label(self.wri_title, 0, PANEL_X, 320 - PANEL_X).value("Tetris")

        self.lbl_score = Label(self.wri, 30, PANEL_X, 320 - PANEL_X)
        self.lbl_lines = Label(self.wri, 45, PANEL_X, 320 - PANEL_X)
        self.lbl_level = Label(self.wri, 60, PANEL_X, 320 - PANEL_X)
        self.lbl_status = Label(self.wri, 85, PANEL_X, 320 - PANEL_X)

        # Next piece preview frame
        self._next_x = PANEL_X
        self._next_y = 105
        self._next_cell = 8
        self._next_w = 4 * self._next_cell
        self._next_h = 4 * self._next_cell
        display.rect(self._next_x - 1, self._next_y - 1, self._next_w + 2, self._next_h + 2, GREY)

        # Board frame
        display.rect(
            BOARD_X - 1,
            BOARD_Y - 1,
            BOARD_W * CELL + 2,
            BOARD_H * CELL + 2,
            GREY,
        )
        display.fill_rect(BOARD_X, BOARD_Y, BOARD_W * CELL, BOARD_H * CELL, BLACK)

        # Button events for discrete actions.
        ev_subset = ButtonEvents.get_event_subset(
            [
                ("btn_u", ButAct.ACT_PRESS),
                ("btn_a", ButAct.ACT_PRESS),
                ("btn_b", ButAct.ACT_PRESS),
                ("btn_start", ButAct.ACT_PRESS),
                ("btn_select", ButAct.ACT_PRESS),
                ("btn_b", ButAct.ACT_LONG),
            ]
        )
        self._be = ButtonEvents(ev_subset)

        # Hold-repeat state
        self._hold_l = False
        self._hold_r = False
        self._hold_d = False
        self._l_next = 0
        self._r_next = 0

        self._next_fall = 0

        # Start game
        self._game.spawn()
        self._update_hud(force=True)
        self._draw_next_preview(force=True)
        self._render_board(force=True)
        ssd.show()

    def after_open(self):
        self._running = True
        if not self._task_tick or self._task_tick.done():
            self._task_tick = self.reg_task(self._tick_loop(), True)
        if not self._task_btn or self._task_btn.done():
            self._task_btn = self.reg_task(self._btn_loop(), True)

    def on_hide(self):
        self._running = False
        for t in (self._task_tick, self._task_btn):
            try:
                if t and not t.done():
                    t.cancel()
            except Exception:
                pass

    def _gravity_ms(self) -> int:
        ms = int(800 * (0.85 ** self._game.level))
        if ms < 100:
            ms = 100
        if self._hold_d:
            ms = 50
        return ms

    def _poll_holds(self, now_ms: int):
        l = BtnConfig.btn_l.value() == 0
        r = BtnConfig.btn_r.value() == 0
        d = BtnConfig.btn_d.value() == 0

        # Soft drop state
        self._hold_d = d

        # If both left/right are held, don't auto-repeat to avoid jitter.
        if l and r:
            self._hold_l = False
            self._hold_r = False
            return

        if l and not self._hold_l:
            self._hold_l = True
            self._l_next = _ticks_add(now_ms, DAS_MS)
            self._try_action(self._game.try_move, -1, 0)
        elif not l:
            self._hold_l = False

        if r and not self._hold_r:
            self._hold_r = True
            self._r_next = _ticks_add(now_ms, DAS_MS)
            self._try_action(self._game.try_move, 1, 0)
        elif not r:
            self._hold_r = False

        if self._hold_l and _ticks_diff(now_ms, self._l_next) >= 0:
            self._l_next = _ticks_add(now_ms, ARR_MS)
            self._try_action(self._game.try_move, -1, 0)
        if self._hold_r and _ticks_diff(now_ms, self._r_next) >= 0:
            self._r_next = _ticks_add(now_ms, ARR_MS)
            self._try_action(self._game.try_move, 1, 0)

    async def _btn_loop(self):
        async for btn, ev in self._be.get_btn_events():
            if not self._running:
                return

            if ev == ButAct.ACT_LONG and btn == "btn_b":
                Screen.back()
                return

            if ev != ButAct.ACT_PRESS:
                continue

            if btn == "btn_select":
                Screen.back()
                return

            if btn == "btn_start":
                self._paused = not self._paused
                self.lbl_status.value("PAUSED" if self._paused else "")
                # Reset fall timer so gravity doesn't "catch up" instantly on resume.
                self._next_fall = _ticks_add(_ticks_ms(), self._gravity_ms())
                continue

            if self._paused or self._game.game_over:
                continue

            if btn in ("btn_u", "btn_a"):
                if self._game.try_rotate_cw():
                    self._render_board()
                continue

            if btn == "btn_b":
                dropped = self._game.hard_drop()
                if dropped:
                    self._game.score += dropped * 2
                self._lock_step()
                continue

    def _try_action(self, fn, *args):
        if self._paused or self._game.game_over:
            return False
        ok = fn(*args)
        if ok:
            self._render_board()
        return ok

    def _lock_step(self):
        self._game.lock_and_clear()
        if not self._game.spawn():
            self._go_game_over()
            return
        self._update_hud()
        self._draw_next_preview()
        self._render_board(force=True)
        self._next_fall = _ticks_add(_ticks_ms(), self._gravity_ms())

    def _go_game_over(self):
        self._game.game_over = True
        self._running = False

        # Update high score.
        if self._game.score > self._hi.best_score:
            self._hi.best_score = self._game.score
            self._hi.best_lines = self._game.lines
            self._hi.best_level = self._game.level
            self._hi.save()

        # Small delay reduces accidental button carryover between screens.
        async def _change():
            await asyncio.sleep_ms(200)
            Screen.change(
                TetrisGameOverScreen,
                mode=Screen.REPLACE,
                kwargs={"score": self._game.score, "hi": self._hi},
            )

        asyncio.create_task(_change())

    async def _tick_loop(self):
        self._next_fall = _ticks_add(_ticks_ms(), self._gravity_ms())
        while self._running:
            now = _ticks_ms()
            self._poll_holds(now)

            if not self._paused and not self._game.game_over:
                if _ticks_diff(now, self._next_fall) >= 0:
                    if self._hold_d:
                        # Soft drop points per step when held.
                        if self._game.try_move(0, 1):
                            self._game.score += 1
                            self._render_board()
                        else:
                            self._lock_step()
                    else:
                        if self._game.try_move(0, 1):
                            self._render_board()
                        else:
                            self._lock_step()
                    self._update_hud()
                    self._next_fall = _ticks_add(now, self._gravity_ms())

            await asyncio.sleep_ms(POLL_MS)

    def _update_hud(self, force: bool = False):
        g = self._game
        if force or g.score != self._last_score:
            self._last_score = g.score
            self.lbl_score.value(f"Score: {g.score}")
        if force or g.lines != self._last_lines:
            self._last_lines = g.lines
            self.lbl_lines.value(f"Lines: {g.lines}")
        if force or g.level != self._last_level:
            self._last_level = g.level
            self.lbl_level.value(f"Level: {g.level}")

    def _draw_next_preview(self, force: bool = False):
        pid = self._game.next_piece_id
        if not force and pid == self._last_next_piece:
            return
        self._last_next_piece = pid

        # Clear preview area
        display.fill_rect(self._next_x, self._next_y, self._next_w, self._next_h, BLACK)

        col = PIECE_COLORS[pid]
        # Show rotation 0
        for dx, dy in PIECES[pid][0]:
            x = self._next_x + dx * self._next_cell
            y = self._next_y + dy * self._next_cell
            display.fill_rect(x, y, self._next_cell - 1, self._next_cell - 1, col)
        ssd.show()

    def _render_board(self, force: bool = False):
        # Composite buffer = locked board + active piece.
        rb = self._render_buf
        bd = self._game.board
        for i in range(len(rb)):
            rb[i] = bd[i]

        active_color_id = self._game.piece_id + 1
        for x, y in self._game._cells_for(
            self._game.piece_id, self._game.rot, self._game.px, self._game.py
        ):
            if 0 <= x < BOARD_W and 0 <= y < BOARD_H:
                rb[y * BOARD_W + x] = active_color_id

        last = self._last_draw
        dirty = False
        for i in range(len(rb)):
            v = rb[i]
            if not force and v == last[i]:
                continue
            last[i] = v
            dirty = True
            x = i % BOARD_W
            y = i // BOARD_W
            color = BLACK if v == 0 else PIECE_COLORS[v - 1]
            px = BOARD_X + x * CELL
            py = BOARD_Y + y * CELL
            display.fill_rect(px, py, CELL - 1, CELL - 1, color)
        if dirty:
            ssd.show()


def badge_game_config():
    return {
        "con_id": 7,
        "title": "Tetris",
        "screen_class": TetrisGameScreen,
        "screen_args": (),
        "multiplayer": False,
        "description": "Solo Tetris minigame",
    }
