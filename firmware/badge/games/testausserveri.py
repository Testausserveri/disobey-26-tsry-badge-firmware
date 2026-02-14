import asyncio
from machine import Pin
from neopixel import NeoPixel

from gui.core.ugui import Screen, ssd
from bdg.config import Config
from bdg.utils import blit, blit_palette, blit_palette_row
from gui.core.writer import CWriter, AlphaColor
from gui.widgets import Label
import gui.fonts.poppins35 as poppins35
from gui.core.colors import WHITE, BLACK
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.bleds import clear_leds, dimm_gamma
from images import testausserveri_bg_anim as bg_anim
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

        self.nick_label = Label(
            self.wri_nick, nick_row, self.nick_col, self.nick_w,
            bdcolor=False, bgcolor=AlphaColor(BLACK),
        )
        self.nick_label.value(self.nick)

        HiddenActiveWidget(self.wri_nick)
        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)
        self.running = True

        self.frame_size = bg_anim.rows * bg_anim.cols
        self.num_frames = bg_anim.num_frames
        self._linebuf = memoryview(bytearray(bg_anim.cols * 2))

    def after_open(self):
        # Draw first frame with logo + label
        blit_palette(ssd.mvb, bg_anim.frames[0], bg_anim.palette, self.frame_size)
        blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)

        # Snapshot pure background in label region BEFORE text rendering
        row_bytes = bg_anim.cols * 2
        self._nick_row0 = self.nick_label.row
        self._nick_rows = self.nick_label.height
        self._nick_col0 = self.nick_label.col
        self._nick_cols = self.nick_label.width
        nick_byte_w = self._nick_cols * 2
        snap_size = self._nick_rows * nick_byte_w
        nick_bg = bytearray(snap_size)
        for r in range(self._nick_rows):
            src = (self._nick_row0 + r) * row_bytes + self._nick_col0 * 2
            dst = r * nick_byte_w
            nick_bg[dst:dst + nick_byte_w] = ssd.mvb[src:src + nick_byte_w]

        self.show(True)  # Renders label widget into mvb + physical refresh

        # Snapshot label region WITH text
        nick_with_text = bytearray(snap_size)
        for r in range(self._nick_rows):
            src = (self._nick_row0 + r) * row_bytes + self._nick_col0 * 2
            dst = r * nick_byte_w
            nick_with_text[dst:dst + nick_byte_w] = ssd.mvb[src:src + nick_byte_w]

        # Build text-only snapshot: text pixels kept, bg pixels set to key color
        KEY0 = 0x01
        KEY1 = 0x00
        self._nick_snap = bytearray(snap_size)
        for i in range(0, snap_size, 2):
            if nick_with_text[i] != nick_bg[i] or nick_with_text[i + 1] != nick_bg[i + 1]:
                self._nick_snap[i] = nick_with_text[i]
                self._nick_snap[i + 1] = nick_with_text[i + 1]
            else:
                self._nick_snap[i] = KEY0
                self._nick_snap[i + 1] = KEY1
        self._nick_key0 = KEY0
        self._nick_key1 = KEY1

        self.reg_task(self.bg_animation(), True)
        self.reg_task(self.led_animation(), True)

    def on_hide(self):
        self.running = False
        clear_leds(self.np)
        self.led_power.value(0)

    def _show_frame(self, frame_data):
        """Render every row: palette bg + logo overlay + label overlay, then SPI-write."""
        linebuf = self._linebuf
        pal = bg_anim.palette
        cols = bg_anim.cols
        row_bytes = cols * 2

        logo_data = logo_img.data
        logo_cols = logo_img.cols
        logo_rows = logo_img.rows
        logo_row0 = self.logo_row
        logo_col0 = self.logo_col
        logo_key0 = logo_data[0]
        logo_key1 = logo_data[1]
        logo_stride = logo_cols * 2

        nick_snap = self._nick_snap
        nick_row0 = self._nick_row0
        nick_rows = self._nick_rows
        nick_col0 = self._nick_col0
        nick_cols = self._nick_cols
        nick_byte_w = nick_cols * 2
        nick_key0 = self._nick_key0
        nick_key1 = self._nick_key1

        spi = ssd._spi
        dc = ssd._dc
        cs = ssd._cs
        if ssd._spi_init:
            ssd._spi_init(spi)
        dc(0)
        cs(0)
        spi.write(b"\x2c")  # RAMWR
        dc(1)

        for row in range(bg_anim.rows):
            # Expand palette row into linebuf
            blit_palette_row(linebuf, frame_data, pal, cols, row * cols)

            # Overlay logo pixels (key-color transparency)
            logo_y = row - logo_row0
            if 0 <= logo_y < logo_rows:
                ls = logo_y * logo_stride
                lc = logo_col0 * 2
                for p in range(logo_cols):
                    si = ls + p * 2
                    if logo_data[si] != logo_key0 or logo_data[si + 1] != logo_key1:
                        di = lc + p * 2
                        linebuf[di] = logo_data[si]
                        linebuf[di + 1] = logo_data[si + 1]

            # Overlay label text (key-color transparency, same as logo)
            nick_y = row - nick_row0
            if 0 <= nick_y < nick_rows:
                ns = nick_y * nick_byte_w
                nc = nick_col0 * 2
                for p in range(nick_cols):
                    si = ns + p * 2
                    if nick_snap[si] != nick_key0 or nick_snap[si + 1] != nick_key1:
                        di = nc + p * 2
                        linebuf[di] = nick_snap[si]
                        linebuf[di + 1] = nick_snap[si + 1]

            spi.write(linebuf)

        cs(1)

    async def bg_animation(self):
        # Pause the framework's auto_refresh — we own the display refresh
        Screen.rfsh_start.clear()
        frames = bg_anim.frames
        idx = 1  # Frame 0 already drawn in after_open
        while self.running:
            self._show_frame(frames[idx])
            idx = (idx + 1) % self.num_frames
            await asyncio.sleep(0.15)
        # Restore auto_refresh when we stop
        Screen.rfsh_start.set()

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
        "con_id": 7,
        "title": "Testausserveri",
        "screen_class": Testausserveri,
        "screen_args": (),
        "multiplayer": False,
        "description": "Testausserveri ry name tag",
    }
