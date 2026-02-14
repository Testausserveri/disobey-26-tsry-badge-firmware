import asyncio
import random
from time import time
from machine import Pin
from neopixel import NeoPixel

try:
    import urequests as requests
except ImportError:
    import requests

from gui.core.ugui import Screen, ssd
from bdg.config import Config
from bdg.utils import blit
from gui.core.writer import CWriter, AlphaColor, Writer
from gui.widgets import Label
from gui.fonts import font10
from fonts import poppins35
from gui.core.colors import WHITE, BLACK, GREY
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.bleds import clear_leds, dimm_gamma
from bdg.asyncbutton import ButtonEvents, ButAct
from images import testausserveri_logo as logo_img

# Try to import animated background support (requires lajp firmware)
try:
    from bdg.utils import blit_palette
    from images import testausserveri_bg_anim as bg_anim
    HAS_ANIMATED_BG = True
except ImportError:
    from images import matriisi as matriisi_img
    HAS_ANIMATED_BG = False

# Nearby friends: opacity decays until next BeaconMsg with same nick
FADE_DECAY = 0.003  # per frame
MIN_OPACITY = 0.05
BOUNCE_SPEED = 8.0   # Speed of floating nicknames
ANIMATION_INTERVAL = 0.08

# Discord stats
DISCORD_API_URL = "https://api.testausserveri.fi/v1/discord/guildInfo?r=memberCount,membersOnline,messagesToday"
DISCORD_FETCH_INTERVAL = 30  # seconds

LOGO_W = logo_img.cols
LOGO_H = logo_img.rows
TEXT_H = 35  # poppins35 font height (for own nick label)
FLOATING_TEXT_H = 10  # font10 height for floating nicks
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
        self.wri_floating = CWriter(ssd, font10, WHITE, AlphaColor(BLACK), verbose=False)
        self.wri_floating.set_clip(True, True, False)  # Clip instead of scroll

        self.nick = Config.config.get("espnow", {}).get("nick", "ANONYMOUS")
        self.nick_w = self.wri_nick.stringlen(self.nick)

        total_w = LOGO_W + GAP + self.nick_w
        self.start_col = max(0, (ssd.width - total_w) // 2)
        self.logo_col = self.start_col
        self.nick_col = self.start_col + LOGO_W + GAP

        max_h = max(LOGO_H, TEXT_H)
        self.logo_row = max(0, (ssd.height - max_h) // 2)
        nick_row = self.logo_row + (LOGO_H - TEXT_H) // 2
        nick_row = max(0, min(nick_row, ssd.height - TEXT_H - 1))

        # Clamp label width so Label stays within screen
        label_w = min(self.nick_w, max(1, ssd.width - self.nick_col - 1))

        self.nick_label = Label(
            self.wri_nick, nick_row, self.nick_col, label_w,
            bdcolor=False, bgcolor=AlphaColor(BLACK),
        )
        self.nick_label.value(self.nick)

        HiddenActiveWidget(self.wri_nick)
        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)
        self.running = True

        # Nearby friends: nick -> {x, y, vx, vy, opacity, last_seen}
        self._floating = {}
        self._floating_lock = asyncio.Lock()

        # Discord stats
        self._discord_stats = None
        self._show_discord_stats = True  # Show by default, toggle with SELECT
        self._be = None  # Button events

        # Animated background (if available)
        if HAS_ANIMATED_BG:
            self.frame_size = bg_anim.rows * bg_anim.cols
            self.num_frames = bg_anim.num_frames

    def after_open(self):
        if HAS_ANIMATED_BG:
            self._after_open_animated()
        else:
            self._after_open_static()

        self.reg_task(self.led_animation(), True)
        # self.reg_task(self._beacon_updates(), True)
        # self.reg_task(self._nearby_friends_animation(), True)
        self.reg_task(self._discord_stats_fetcher(), True)
        self.reg_task(self._button_handler(), True)

    def _after_open_animated(self):
        """Set up animated background with nick text snapshotting."""
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

        self.reg_task(self._bg_animation_loop(), True)

    def _after_open_static(self):
        """Set up static background (fallback when animated bg not available)."""
        blit(ssd, matriisi_img, 0, 0)
        blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)
        self.show(True)
        self.reg_task(self._static_redraw_loop(), True)

    def on_hide(self):
        self.running = False
        clear_leds(self.np)
        self.led_power.value(0)
        if self._be:
            self._be.close()

    # --- Rendering helpers ---

    def _overlay_nick_snap(self):
        """Overlay the pre-snapshotted nick text onto ssd.mvb."""
        nick_snap = self._nick_snap
        nick_row0 = self._nick_row0
        nick_rows = self._nick_rows
        nick_col0 = self._nick_col0
        nick_cols = self._nick_cols
        nick_byte_w = nick_cols * 2
        nick_key0 = self._nick_key0
        nick_key1 = self._nick_key1
        row_bytes = ssd.width * 2
        mvb = ssd.mvb

        for r in range(nick_rows):
            ns = r * nick_byte_w
            ds = (nick_row0 + r) * row_bytes + nick_col0 * 2
            for p in range(nick_cols):
                si = ns + p * 2
                if nick_snap[si] != nick_key0 or nick_snap[si + 1] != nick_key1:
                    di = ds + p * 2
                    mvb[di] = nick_snap[si]
                    mvb[di + 1] = nick_snap[si + 1]

    def _draw_floating_nicks(self):
        """Draw floating nicknames onto current framebuffer."""
        for nick, p in self._floating.items():
            if p["opacity"] < MIN_OPACITY:
                continue
            fg = self._fgcolor_for_opacity(p["opacity"])
            self.wri_floating.setcolor(fg, AlphaColor(BLACK))
            Writer.set_textpos(ssd, int(p["y"]), int(p["x"]))
            self.wri_floating.printstring(nick)
            self.wri_floating.setcolor()

    def _draw_discord_stats(self):
        """Draw Discord stats in top left corner."""
        if not self._show_discord_stats:
            return

        try:
            self.wri_floating.setcolor(WHITE, AlphaColor(BLACK))

            if self._discord_stats is None or "error" in self._discord_stats:
                return  # No data yet or no WiFi -- just hide stats
            else:
                members_online = self._discord_stats.get("membersOnline", 0)
                member_count = self._discord_stats.get("memberCount", 0)
                messages_today = self._discord_stats.get("messagesToday", 0)

                Writer.set_textpos(ssd, 2, 2)
                self.wri_floating.printstring(f"Members: {members_online}/{member_count} | Messages: {messages_today}")

            self.wri_floating.setcolor()
        except Exception as e:
            print(f"Error drawing Discord stats: {e}")

    def _fgcolor_for_opacity(self, opacity):
        if opacity > 0.6:
            return WHITE
        if opacity > 0.2:
            return GREY
        return BLACK

    # --- Background rendering loops ---

    async def _bg_animation_loop(self):
        """Animated background loop -- renders each frame with all overlays."""
        Screen.rfsh_start.clear()
        frames = bg_anim.frames
        pal = bg_anim.palette
        idx = 1  # Frame 0 already drawn in after_open
        while self.running:
            # Render background frame into framebuffer
            blit_palette(ssd.mvb, frames[idx], pal, self.frame_size)
            # Overlay logo
            blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)
            # Overlay nick text snapshot
            self._overlay_nick_snap()
            # Overlay floating friends
            self._draw_floating_nicks()
            # Overlay discord stats
            self._draw_discord_stats()
            # Flush to display
            ssd.show()
            idx = (idx + 1) % self.num_frames
            await asyncio.sleep(0.15)
        # Restore auto_refresh when we stop
        Screen.rfsh_start.set()

    async def _static_redraw_loop(self):
        """Static background redraw loop (fallback when no animated bg)."""
        while self.running:
            await asyncio.sleep(ANIMATION_INTERVAL)
            # Redraw static background, logo, and all overlays
            blit(ssd, matriisi_img, 0, 0)
            blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)
            self._draw_floating_nicks()
            self._draw_discord_stats()
            self.show(True)

    # --- Async feature tasks ---

    async def _discord_stats_fetcher(self):
        """Connect WiFi once, then fetch Discord stats every 10 seconds."""
        import network
        sta = network.WLAN(network.STA_IF)

        # Try to connect WiFi (don't touch sta.active -- ESP-NOW needs it)
        if not sta.isconnected():
            ota_cfg = Config.config.get("ota", {})
            wifi_cfg = ota_cfg.get("wifi", {})
            ssid = wifi_cfg.get("ssid")
            password = wifi_cfg.get("password")

            if ssid:
                sta.connect(ssid, password)
                for _ in range(30):  # wait up to 15s
                    if sta.isconnected():
                        break
                    await asyncio.sleep_ms(500)

        # Fetch loop
        while self.running:
            if not sta.isconnected():
                self._discord_stats = {"error": "No WiFi"}
            else:
                try:
                    response = requests.get(DISCORD_API_URL, timeout=5)
                    if response.status_code == 200:
                        self._discord_stats = response.json()
                    response.close()
                except Exception as e:
                    print(f"Failed to fetch Discord stats: {e}")
            await asyncio.sleep(DISCORD_FETCH_INTERVAL)

    async def _button_handler(self):
        """Handle button press to toggle Discord stats display."""
        ev_subset = ButtonEvents.get_event_subset(
            [
                ("btn_select", ButAct.ACT_PRESS),
            ]
        )
        self._be = ButtonEvents(ev_subset)

        async for btn, ev in self._be.get_btn_events():
            if not self.running:
                return
            if btn == "btn_select" and ev == ButAct.ACT_PRESS:
                self._show_discord_stats = not self._show_discord_stats
                print(f"Discord stats display: {self._show_discord_stats}")

    async def _beacon_updates(self):
        from bdg.msg.connection import NowListener

        try:
            async for _ in NowListener.updates():
                if not self.running:
                    return
                latest = NowListener.last_seen.latest()
                if latest is None:
                    continue
                nick = latest.nick if isinstance(latest.nick, str) else latest.nick.decode("utf-8")
                if nick == self.nick:
                    continue
                async with self._floating_lock:
                    if nick not in self._floating:
                        nw = self.wri_floating.stringlen(nick)
                        max_x = max(0, ssd.width - nw - 4)
                        max_y = max(0, ssd.height - FLOATING_TEXT_H - 8)
                        self._floating[nick] = {
                            "x": random.randint(4, max_x) if max_x > 4 else 4,
                            "y": random.randint(4, max_y) if max_y > 4 else 4,
                            "vx": (random.random() * 2 - 1) * BOUNCE_SPEED,
                            "vy": (random.random() * 2 - 1) * BOUNCE_SPEED,
                            "opacity": 1.0,
                            "last_seen": time(),
                        }
                    else:
                        self._floating[nick]["opacity"] = 1.0
                        self._floating[nick]["last_seen"] = time()
        except asyncio.CancelledError:
            pass

    async def _nearby_friends_animation(self):
        """Update floating nick positions and opacity (rendering handled by bg loop)."""
        while self.running:
            await asyncio.sleep(ANIMATION_INTERVAL)
            async with self._floating_lock:
                to_remove = []
                for nick, p in self._floating.items():
                    nw = self.wri_floating.stringlen(nick)
                    p["x"] += p["vx"]
                    p["y"] += p["vy"]
                    if p["x"] <= 0 or p["x"] >= ssd.width - nw - 2:
                        p["vx"] = -p["vx"]
                        p["x"] = max(0, min(p["x"], ssd.width - nw - 2))
                    if p["y"] <= 0 or p["y"] >= ssd.height - FLOATING_TEXT_H - 6:
                        p["vy"] = -p["vy"]
                        p["y"] = max(0, min(p["y"], ssd.height - FLOATING_TEXT_H - 6))
                    p["opacity"] = max(0, p["opacity"] - FADE_DECAY)
                    if p["opacity"] < MIN_OPACITY:
                        to_remove.append(nick)
                for nick in to_remove:
                    del self._floating[nick]

    async def led_animation(self):
        colors = dimm_gamma(
            [(0, 0, 255), (0, 100, 255), (0, 200, 255), (0, 255, 255)],
            0.1,
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
