from gui.core.colors import GREEN, BLACK
from gui.fonts import font6, font10, font14, arial35
from gui.core.ugui import Screen, ssd, display, Widget
from gui.core.writer import CWriter
from gui.widgets import Label, Button, RadioButtons, LED
import asyncio
from gui.core.colors import *
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
import random
from bdg.msg.connection import Connection, Beacon
from bdg.asyncbutton import ButtonEvents, ButAct
from bdg.msg import AppMsg, BadgeMsg


@AppMsg.register
class ReactionStart(BadgeMsg):
    """Exchange random seeds between badges"""
    def __init__(self, my_seed: int):
        super().__init__()
        self.my_seed = my_seed


@AppMsg.register
class ReactionEnd(BadgeMsg):
    """Send final score when game over"""
    def __init__(self, final_score: int):
        super().__init__()
        self.final_score = final_score


DARKYELLOW = create_color(12, 104, 114, 45)
DIS_RED = create_color(13, 210, 0, 0)
DIS_PINK = create_color(14, 240, 0, 240)
# c: color, hc: highlight color
GAME_BTN_COLORS = [
    {"hc": GREEN, "c": LIGHTGREEN, "btn": "btn"},
    {"hc": BLUE, "c": DARKBLUE, "btn": "btn_select"},
    {"hc": YELLOW, "c": DARKYELLOW, "btn": "btn_a"},
    {"hc": RED, "c": LIGHTRED, "btn": "btn_b"},
]


class ReactionButton(Widget):
    def __init__(self, writer, row, col, radius, color, hl_color):
        #  Retract 2 pixels to count borders
        radius -= 2
        super().__init__(
            writer, row, col, radius * 2, radius * 2, color, color, False, False
        )
        self.radius = radius
        self.active = False
        self.hl = False
        self.hl_color = hl_color

    def show(self):
        if super().show():
            c = self.hl_color if self.hl else self.fgcolor

            display.fillcircle(
                self.col + self.radius, self.row + self.radius, self.radius, c
            )
            if self.active:
                self.draw_bd(WHITE)
            else:
                self.draw_bd(c)

    def set_act(self, v: bool):
        self.active = v
        self.draw = True  # trigger redraw

    def set_hl(self, v: bool):
        self.hl = v
        self.draw = True

    def draw_bd(self, color):
        display.circle(
            self.col + self.radius, self.row + self.radius, self.radius + 1, color
        )
        display.circle(
            self.col + self.radius, self.row + self.radius, self.radius + 2, color
        )


class GameOver(Exception):
    def __init__(self, points, reason=""):
        super().__init__()
        self.points = points
        self.reason = reason


class GameWin(Exception):
    def __init__(self, points):
        super().__init__()
        self.points = points


class ReactionGameMultiplayerEndScr(Screen):
    """End screen for multiplayer reaction game"""
    color_map[FOCUS] = DIS_PINK

    def __init__(self, points: int, conn: Connection, opponent_score: int = None,
                 result: str = None, waiting: bool = False):
        super().__init__()
        print(f"EndScr init: {points=}, {opponent_score=}, {result=}, {waiting=}")
        
        self.conn = conn
        self.my_score = points
        self.opponent_score = opponent_score
        self.result = result
        self.waiting = waiting

        wri_title = CWriter(ssd, arial35, WHITE, BLACK, verbose=False)
        self.title_label = Label(wri_title, 20, 0, 320, justify=Label.CENTRE)
        
        wri_score = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        self.score_label = Label(wri_score, 70, 0, 320, justify=Label.CENTRE)
        
        if waiting:
            print("Setting waiting text")
            self.title_label.value(text="Waiting...")
            self.score_label.value(text=f"Your score: {points}")
        else:
            # Show result
            print(f"Setting result text: {result}")
            if result == "won":
                self.title_label.value(text="You Won!")
            elif result == "lost":
                self.title_label.value(text="You Lost!")
            else:
                self.title_label.value(text="Draw!")
            
            self.score_label.value(text=f"You: {points} | Opp: {opponent_score}")
        
        print("EndScr init complete")
    
    def after_open(self):
        # If waiting for opponent, keep reading messages
        if self.waiting:
            print("Registering message reader for waiting screen")
            self.reg_task(self.wait_for_opponent(), True)
    
    async def wait_for_opponent(self):
        """Continue reading messages while waiting for opponent to finish"""
        if not self.conn or not self.conn.active:
            print("wait_for_opponent: conn not active")
            return
        
        async for msg in self.conn.get_msg_aiter():
            print(f"EndScr received message: {msg.msg_type}")
            
            if msg.msg_type == "ReactionEnd":
                opponent_score = msg.final_score
                print(f"Opponent finished with score: {opponent_score}")
                
                # Determine result
                if self.my_score > opponent_score:
                    result = "won"
                elif self.my_score < opponent_score:
                    result = "lost"
                else:
                    result = "draw"
                
                print(f"Final result: {result} (Me: {self.my_score}, Opp: {opponent_score})")
                
                # Update screen to show results
                Screen.change(
                    ReactionGameMultiplayerEndScr,
                    mode=Screen.REPLACE,
                    kwargs={
                        "points": self.my_score,
                        "conn": self.conn,
                        "opponent_score": opponent_score,
                        "result": result,
                        "waiting": False
                    }
                )
                break

    def on_hide(self):
        # Resume beacon and cleanup
        Beacon.suspend(False)
        if self.conn:
            asyncio.create_task(self.conn.terminate(send_out=True))


class ReactionGameScr(Screen):

    STATE_GAME_PAUSED = 0
    STATE_GAME_ONGOING = 1
    STATE_GAME_OVER = 2

    # Game's state
    game = None
    # Game task
    gt = None
    # Button task
    bt = None
    # Game UI state
    gs = STATE_GAME_PAUSED

    def __init__(self, conn: Connection):
        # Multiplayer only - connection required
        self.conn: Connection = conn
        
        # Multiplayer state
        self.my_seed = None
        self.opponent_seed = None
        self.opponent_finished = False
        self.opponent_score = None
        self.my_final_score = None
        self.waiting_for_opponent = False
        
        super().__init__()
        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)

        HiddenActiveWidget(self.wri)

        self.btns = []
        self.higlight_tasks = {}

        height = 42
        spacing = 15
        btn_cnt = len(GAME_BTN_COLORS)
        btns_width = btn_cnt * height + (btn_cnt - 1) * spacing
        pos_y = int((320 - btns_width) / 2)

        self.btn_idx = {}
        for i, btn in enumerate(GAME_BTN_COLORS):
            self.btns.append(
                ReactionButton(self.wri, 100, pos_y, 20, btn["c"], btn["hc"])
            )
            self.btn_idx[btn["btn"]] = i
            pos_y += height + spacing

        self.wri_points = CWriter(ssd, arial35, WHITE, BLACK, verbose=False)
        self.lbl_points = Label(self.wri_points, 20, 0, 320, justify=Label.CENTRE)

        ev_subset = ButtonEvents.get_event_subset(
            [
                ("btn_a", ButAct.ACT_PRESS),
                ("btn_b", ButAct.ACT_PRESS),
                ("btn_b", ButAct.ACT_LONG),
                ("btn_select", ButAct.ACT_PRESS),
                ("btn_start", ButAct.ACT_PRESS),
            ]
        )
        self.be = ButtonEvents(ev_subset)

    async def btn_handler(self):
        async for btn, ev in self.be.get_btn_events():
            if ev == ButAct.ACT_LONG and btn == "btn_b":
                self.go_back()
            elif self.gs == self.STATE_GAME_ONGOING:
                print(f"btn: {btn}, ev: {ev}")
                if ev == ButAct.ACT_PRESS and btn in self.btn_idx:
                    await self.btn_cb(self.btn_idx[btn])

    def go_back(self):
        # TODO: Should we show popup to confirm leaving game?
        if self.gs == self.STATE_GAME_ONGOING:
            print("game ongoing, can't exit!")
        elif self.gs == self.STATE_GAME_OVER:
            Screen.back()

    def after_open(self):
        # Always register button handler first
        if not self.bt or self.bt.done():
            self.bt = self.reg_task(self.btn_handler(), True)
        
        # Suspend beacon during multiplayer game
        Beacon.suspend(True)
        
        # Register message reading task
        self.reg_task(self.read_messages(), True)
        
        # Generate and send our seed immediately
        my_seed = random.randint(10_000, 100_000)
        self.my_seed = my_seed
        print(f"Connection active: {self.conn.active}")
        print(f"Sending my seed: {my_seed}")
        self.conn.send_app_msg(ReactionStart(my_seed), sync=False)

    def on_hide(self):
        self.gs = self.STATE_GAME_PAUSED
        print("screen hidden")
        # Don't cleanup here - let the end screen handle it

    async def cont_sqnc(self):
        await asyncio.sleep(1.5)
        self.gs = self.STATE_GAME_ONGOING
        print("cont_sqnc")
        try:
            while self.game.has_next_step():
                print("cont_sqnc: has next step")
                if self.gs == self.STATE_GAME_OVER:
                    print("state is game over")
                    break

                btn_idx = self.game.next_step()
                print(f"Button index: {btn_idx}")
                await self.hl_button(btn_idx, self.game.cur_idx)
        except GameOver as go:
            print(f"GameOver exception caught: {go.points}")
            self.gs = self.STATE_GAME_OVER
            # Schedule stop_game as separate task to avoid blocking
            asyncio.create_task(self.stop_game())
        

    async def btn_cb(self, btn_idx):
        print(f"game state: {self.gs} {btn_idx=}")
        if self.gs == self.STATE_GAME_ONGOING:
            self.higlight_btn(btn_idx)
            try:
                self.game.btn_press(btn_idx)
                self.lbl_points.value(text=str(self.game.points()))
            except GameOver as go:
                # Schedule stop_game as separate task to avoid "can't cancel self"
                asyncio.create_task(self.stop_game())
            except GameWin as go:
                # Schedule stop_game as separate task to avoid "can't cancel self"
                asyncio.create_task(self.stop_game())

    async def _highlight_off(self, btn_idx):
        await asyncio.sleep(0.5)
        self.btns[btn_idx].set_act(False)

    def higlight_btn(self, btn_idx):
        # highlight button with separate task and reschedule highlight
        # if button pressed again during wait time
        self.btns[btn_idx].set_act(True)
        if btn_idx in self.higlight_tasks and not self.higlight_tasks[btn_idx].done():
            self.higlight_tasks[btn_idx].cancel()
        self.higlight_tasks[btn_idx] = asyncio.create_task(self._highlight_off(btn_idx))

    async def hl_button(self, btn_idx, step):
        self.btns[btn_idx].set_hl(True)
        hl_time = 0.2 * (0.99**step)
        await asyncio.sleep(hl_time)
        print(f"hl_time {hl_time}")
        self.btns[btn_idx].set_hl(False)

        base_sleep_time = max(0.2, 1.0 * (0.9**step))
        random_factor = 1  # random.uniform(0.8, 1.2)
        sleep_time = base_sleep_time * random_factor
        print(f"sleep_time {sleep_time}")
        await asyncio.sleep(sleep_time)

    async def read_messages(self):
        """Read incoming messages from opponent"""
        # Check if connection is active (like tictac does)
        if not self.conn or not self.conn.active:
            print("read_messages() stopped, conn not active")
            return
        
        print("Starting message reading loop")
        async for msg in self.conn.get_msg_aiter():
            print(f"Received message: {msg.msg_type}")
            
            if msg.msg_type == "ReactionStart":
                # Received opponent's seed
                self.opponent_seed = msg.my_seed
                combined_seed = self.my_seed + self.opponent_seed
                print(f"Seeds combined: {self.my_seed} + {self.opponent_seed} = {combined_seed}")
                
                # Start the game with synchronized seed
                if not self.game:
                    self.game = RGame(combined_seed)
                
                if not self.gt or self.gt.done():
                    self.gt = self.reg_task(self.cont_sqnc(), True)
            
            elif msg.msg_type == "ReactionEnd":
                # Opponent finished their game
                self.opponent_finished = True
                self.opponent_score = msg.final_score
                print(f"Opponent finished with score: {msg.final_score}, my waiting: {self.waiting_for_opponent}")
                
                # If we already finished, compare scores and show result
                if self.waiting_for_opponent:
                    print("Both finished, showing result now")
                    # Schedule as separate task to avoid blocking message loop
                    asyncio.create_task(self.show_multiplayer_result())
                else:
                    print("Opponent finished first, we're still playing")
                # Otherwise, just save the score and continue playing silently

    async def show_multiplayer_result(self):
        """Compare scores and show result screen"""
        my_score = self.my_final_score
        opp_score = self.opponent_score
        
        if my_score > opp_score:
            result = "won"
        elif my_score < opp_score:
            result = "lost"
        else:
            result = "draw"
        
        print(f"Game result: {result} (Me: {my_score}, Opponent: {opp_score})")
        Screen.change(
            ReactionGameMultiplayerEndScr,
            mode=Screen.REPLACE,
            kwargs={
                "points": my_score,
                "conn": self.conn,
                "opponent_score": opp_score,
                "result": result,
                "waiting": False
            }
        )

    async def stop_game(self):
        self.gs = self.STATE_GAME_OVER
        points = self.game.points()
        print(f"Game Over. {points=}")
        
        self.my_final_score = points
        
        # Send our score to opponent
        try:
            print(f"Sending ReactionEnd with points={points}")
            self.conn.send_app_msg(ReactionEnd(points), sync=False)
        except Exception as e:
            print(f"Failed to send ReactionEnd: {e}")
        
        # Small delay to ensure message is sent before screen change
        await asyncio.sleep_ms(100)
        
        # Check if opponent already finished
        if self.opponent_finished:
            # Both finished, show result immediately
            print("Opponent already finished, showing results")
            # Schedule as separate task
            asyncio.create_task(self.show_multiplayer_result())
        else:
            # Wait for opponent to finish
            print("Waiting for opponent to finish")
            self.waiting_for_opponent = True
            await asyncio.sleep_ms(100)
            Screen.change(
                ReactionGameMultiplayerEndScr,
                mode=Screen.REPLACE,
                kwargs={
                    "points": points,
                    "conn": self.conn,
                    "opponent_score": None,
                    "result": None,
                    "waiting": True
                }
            )


class RGame:
    def __init__(self, seed: int, size: int = 300):
        random.seed(seed)

        self.sqnc = [random.randint(0, 3) for _ in range(size)]
        self.size = size
        self.cur_idx = 0
        self.btn_seq_idx = 0

    def has_next_step(self) -> bool:
        if self.cur_idx - self.btn_seq_idx > 5:
            print("Too much behind {self.cur_idx - self.btn_seq_idx=}")
            raise GameOver(points=self.points(), reason="You are too far behind!")

        return self.cur_idx <= self.size

    def next_step(self) -> int:
        step = self.sqnc[self.cur_idx]
        self.cur_idx += 1
        return step

    def btn_press(self, btn_idx: int):
        print(
            f"btn_press - {btn_idx=} - { self.sqnc[self.btn_seq_idx]=}"
            f" - {self.btn_seq_idx=}"
        )
        if btn_idx != self.sqnc[self.btn_seq_idx]:
            raise GameOver(points=self.points())

        if self.btn_seq_idx == self.size - 1:
            # +1 because index starts at 0
            raise GameWin(points=self.points() + 1)

        self.btn_seq_idx += 1

    def points(self):
        return self.btn_seq_idx


def badge_game_config():
    """
    Configuration for Reaction Game registration.

    Returns:
        dict: Game configuration with con_id, title, screen_class, etc.
    """
    return {
        "con_id": 2,
        "title": "Reaction Game (Dev)",
        "screen_class": ReactionGameScr,
        "screen_args": (),  # Connection passed separately by framework
        "multiplayer": True,
        "description": "Fast-paced reaction speed challenge between badges",
    }
