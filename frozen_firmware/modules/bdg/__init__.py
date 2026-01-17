import asyncio

import gui.fonts.freesans20 as font
from gui.core.colors import *
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets.dialog import DialogBox

from bdg.utils import change_app
from bdg.asyncbutton import ButtonEvents, ButAct
from bdg.screens.loading_screen import LoadingScreen
from bdg.screens.scan_screen import ScannerScreen
from bdg.screens.option_screen import OptionScreen
from bdg.msg.connection import Connection
from bdg.game_registry import get_registry
from bdg.badge_game import GameLobbyScr


def handle_back(ev):
    print(f"[__Back]")
    if Screen.current_screen.parent is not None:
        Screen.back()
    else:
        print("No screen to go back to")


async def global_buttons(espnow=None, sta=None):
    ev_subset = ButtonEvents.get_event_subset(
        [
            ("btn_select", ButAct.ACT_DOUBLE),
            ("btn_b", ButAct.ACT_LONG),
            ("btn_start", ButAct.ACT_LONG),
        ],
    )

    be = ButtonEvents(events=ev_subset)
    base_screen = GameLobbyScr

    handlers = {
        "btn_select": lambda ev: print(f"btn_select {ev}")
        or change_app(
            OptionScreen, kwargs={"espnow": espnow, "sta": sta}, base_screen=base_screen
        ),
        "btn_b": handle_back,
        "btn_start": lambda ev: print(f"btn_start {ev}")
        or change_app(ScannerScreen, base_screen=base_screen),
    }

    async for btn, ev in be.get_btn_events():
        handlers.get(btn, lambda e: print(f"Unknown {btn} {e}"))(ev)


async def new_con_cb(conn: Connection, req=False):
    """
    Handles an incoming connection request by presenting the user with a
    dialog box to accept or decline the connection.

    Handles self initiated connection if req=True
    """
    accept = False
    if not req:
        w_reply = asyncio.Event()

        def resp(window):
            nonlocal accept
            # convert response to True
            print(f"con accept: {window.value()=}")
            accept = window.value() == "Yes"
            w_reply.set()

        wri = CWriter(ssd, font, GREEN, BLACK, verbose=False)

        kwargs = {
            "writer": wri,
            "row": 20,
            "col": 20,
            "elements": (("Yes", GREEN), ("No", RED)),
            "label": "Incoming connection",
            "callback": resp,
            "closebutton": False,
        }

        # show the dialog box
        Screen.change(DialogBox, kwargs=kwargs)

        try:
            # this will block until dialog callback resp() is called or timeout
            await asyncio.wait_for(w_reply.wait(), 15)
        except asyncio.TimeoutError:
            DialogBox.close()  # close dialog

    if accept or req:
        # TODO: change the app that conn was opened
        # Simulate start of App
        if isinstance(Screen.current_screen, OptionScreen):
            # If at home screen add app on top
            mode = Screen.STACK
        else:
            # if we have other app on, replace it
            print(f"Con: Screen.REPLACE {Screen.current_screen=}")
            mode = Screen.REPLACE

        # Get game configuration from registry
        registry = get_registry()
        game_config = registry.get_game(conn.con_id)

        if game_config:
            # Build screen arguments
            screen_args = (conn,) + game_config.get("screen_args", ())

            Screen.change(
                LoadingScreen,
                mode=mode,
                kwargs={
                    "title": game_config["title"],
                    "wait": 10,
                    "nxt_scr": game_config["screen_class"],
                    "scr_args": screen_args,
                },
            )
        else:
            print(f"Warning: No game registered for con_id {conn.con_id}")

    return accept
