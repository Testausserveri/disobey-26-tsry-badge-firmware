import asyncio
from machine import Pin
from neopixel import NeoPixel

from gui.core.ugui import Screen, ssd
from bdg.config import Config
from bdg.utils import blit
from gui.core.writer import CWriter, AlphaColor
from gui.widgets import Label
from fonts import poppins35
from gui.core.colors import WHITE, BLACK
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.bleds import clear_leds, dimm_gamma
from images import matriisi as matriisi_img
from images import testausserveri_logo as logo_img

LOGO_W = logo_img.cols
LOGO_H = logo_img.rows
TEXT_H = 35  # poppins35 font height
GAP = 8


def blit_keyed(ssd, img, row, col):
    """Blit image skipping pixels that match the first pixel (background key)."""
    data = img.data
    key0 = data[0]
    key1 = data[1]
    mvb = ssd.mvb
    irows = min(img.rows, ssd.height - row)
    icols = min(img.cols, ssd.width - col)
    ibytes = img.cols * 2
    dwidth = ssd.width * 2
    d = (row * ssd.width + col) * 2
    s = 0
    while irows:
        for p in range(icols):
            si = s + p * 2
            if data[si] != key0 or data[si + 1] != key1:
                di = d + p * 2
                mvb[di] = data[si]
                mvb[di + 1] = data[si + 1]
        s += ibytes
        d += dwidth
        irows -= 1


class Testausserveri(Screen):
    def __init__(self):
        super().__init__()

        self.wri_nick = CWriter(ssd, poppins35, WHITE, AlphaColor(BLACK), verbose=False)

        self.nick = Config.config.get("espnow", {}).get("nick", "ANONYMOUS")
        self.nick_w = self.wri_nick.stringlen(self.nick)

        total_w = LOGO_W + GAP + self.nick_w
        self.start_col = max(0, (320 - total_w) // 2)
        self.logo_col = self.start_col
        self.nick_col = self.start_col + LOGO_W + GAP

        max_h = max(LOGO_H, TEXT_H)
        self.logo_row = (170 - max_h) // 2
        nick_row = self.logo_row + (LOGO_H - TEXT_H) // 2

        Label(
            self.wri_nick, nick_row, self.nick_col, self.nick_w,
            bdcolor=False, bgcolor=AlphaColor(BLACK),
        ).value(self.nick)

        HiddenActiveWidget(self.wri_nick)
        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)
        self.running = True

    def after_open(self):
        blit(ssd, matriisi_img, 0, 0)
        blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)
        self.show(True)
        self.reg_task(self.led_animation(), True)

    def on_hide(self):
        self.running = False
        clear_leds(self.np)
        self.led_power.value(0)

    async def led_animation(self):
        colors = dimm_gamma(
            [(0, 0, 255), (0, 100, 255), (0, 200, 255), (0, 255, 255)],
            0.4,
        )
        idx = 0
        while self.running:
            for i in range(len(self.np)):
                self.np[i] = colors[(idx + i) % len(colors)]
            self.np.write()
            idx += 1
            await asyncio.sleep(0.4)


def badge_game_config():
    return {
        "con_id": 8,
        "title": "Testausserveri",
        "screen_class": Testausserveri,
        "screen_args": (),
        "multiplayer": False,
        "description": "Testausserveri ry name tag",
    }
