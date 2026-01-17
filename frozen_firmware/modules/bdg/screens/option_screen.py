import asyncio

from bdg.game_registry import init_game_registry, get_registry
import gui.fonts.freesans20 as font
from gui.core.colors import *
from gui.core.ugui import Screen, ssd, quiet
from gui.core.writer import CWriter
from bdg.utils import blit
from images import boot as screen1

from gui.widgets import Label, Button, CloseButton, Listbox
from bdg.badge_game import GameLobbyScr
from bdg.screens.ota import OTAScreen
from bdg.config import Config
from bdg.version import Version


class OptionScreen(Screen):
    sync_update = True  # set screen update mode synchronous

    def __init__(self, espnow = None, sta = None):
        super().__init__()
        # verbose default indicates if fast rendering is enabled
        wri = CWriter(ssd, font, GREEN, BLACK, verbose=False)
        self.els = [
            "Home",
            "Firmware update",
            "---",
        ]

        self.espnow = espnow
        self.sta = sta

        # Add solo games from registry
        registry = get_registry()
        solo_games = registry.get_solo_games()
        for game in solo_games:
            self.els.append(game.get("title", "Unknown Game"))

        self.lb = Listbox(
            wri,
            50,
            50,
            elements=self.els,
            dlines=3,
            bdcolor=RED,
            value=1,
            callback=self.lbcb,
            also=Listbox.ON_LEAVE,
        )

        # Test of movable sprite object with disobey (:
        # self.sprite = Sprite(wri, 40, 150, sprite)
        # self.sprite.visible = False  # update_sprite task will take over.

        CloseButton(wri)  # Quit the application

    def on_open(self):
        # register callback that will make new connection dialog to pop up
        pass

    def on_hide(self):
        # executed when any other window is opened on top
        pass

    def after_open(self):
        # copy_img_to_mvb('screen1.bin', ssd)
        #blit(ssd, screen1, 0, 0)  # show background
        self.show(True)  #
        # self.sprite.capture_bg()  #  capture new background for sprite
        # task will set sprite visible
        # self.reg_task(self.update_sprite(), True)

    async def update_sprite(self):
        # example of using sprite
        print(">>>> new update_sprite task")
        x = self.sprite.col
        y = self.sprite.row
        t = 0.0
        await asyncio.sleep(1)
        self.sprite.visible = True
        try:
            while True:
                self.sprite.update(
                    y + int(cos(t) * 10.0),
                    x + int(sin(t) * 20.0),
                    True,
                )
                await asyncio.sleep_ms(50)
                t += 0.3
        except asyncio.CancelledError:
            self.sprite.visible = False

    def lbcb(self, lb):  # Listbox callback
        selected = lb.textvalue()

        if selected == "Home":
            Screen.change(GameLobbyScr)
        elif selected == "Firmware update":
            # TODO: pass actual connection info (espnow and sta)

            Screen.change(
                OTAScreen,
                mode=Screen.STACK,
                kwargs={
                    "espnow": self.espnow,
                    "sta": self.sta,
                    "fw_version": Version().version,
                    "ota_config": Config.config["ota"],
                },
            )
        elif selected == "---":
            # Separator, do nothing
            pass
        else:
            # Check if it's a solo game
            registry = get_registry()
            for game in registry.get_solo_games():
                if game.get("title") == selected:
                    # Launch the solo game with no connection
                    screen_class = game.get("screen_class")
                    screen_args = game.get("screen_args", ())
                    # Solo games get None as connection
                    Screen.change(
                        screen_class, args=(None,) + screen_args, mode=Screen.STACK
                    )
                    break
