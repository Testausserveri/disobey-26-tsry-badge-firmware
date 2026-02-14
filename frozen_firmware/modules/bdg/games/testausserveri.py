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
from images import matriisi as matriisi_img
from images import testausserveri_logo as logo_img

# Nearby friends: opacity decays until next BeaconMsg with same nick
FADE_DECAY = 0.015  # per frame
MIN_OPACITY = 0.05
BOUNCE_SPEED = 6.0  # Speed of floating nicknames
ANIMATION_INTERVAL = 0.08

# Discord stats
DISCORD_API_URL = "https://api.testausserveri.fi/v1/discord/guildInfo?r=memberCount,membersOnline,messagesToday"
DISCORD_FETCH_INTERVAL = 10  # seconds

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

        print("moj")
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

        Label(
            self.wri_nick, nick_row, self.nick_col, label_w,
            bdcolor=False, bgcolor=AlphaColor(BLACK),
        ).value(self.nick)

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

    def after_open(self):
        blit(ssd, matriisi_img, 0, 0)
        blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)
        self.show(True)
        self.reg_task(self.led_animation(), True)
        self.reg_task(self._beacon_updates(), True)
        self.reg_task(self._nearby_friends_animation(), True)
        self.reg_task(self._discord_stats_fetcher(), True)
        self.reg_task(self._button_handler(), True)

    def on_hide(self):
        self.running = False
        clear_leds(self.np)
        self.led_power.value(0)
        if self._be:
            self._be.close()

    async def _discord_stats_fetcher(self):
        """Connect to WiFi and fetch Discord stats every 10 seconds."""
        import network
        sta = network.WLAN(network.STA_IF)
        
        # Get WiFi credentials from config
        ota_cfg = Config.config.get("ota", {})
        wifi_cfg = ota_cfg.get("wifi", {})
        ssid = wifi_cfg.get("ssid")
        password = wifi_cfg.get("password")
        
        if not ssid:
            print("Discord stats: No WiFi SSID configured, skipping")
            self._discord_stats = {"error": "No WiFi"}
            return
        
        # Connect to WiFi (ESP-NOW keeps working alongside)
        if not sta.isconnected():
            print(f"Discord stats: Connecting to WiFi '{ssid}'...")
            sta.active(True)
            await asyncio.sleep_ms(100)
            sta.connect(ssid, password)
            
            # Wait for connection (max 15 seconds)
            for _ in range(30):
                if sta.isconnected():
                    break
                await asyncio.sleep_ms(500)
            
            if sta.isconnected():
                print(f"Discord stats: WiFi connected! IP={sta.ifconfig()[0]}")
            else:
                print(f"Discord stats: WiFi connection failed")
                self._discord_stats = {"error": "WiFi failed"}
                self._redraw()
                return
        
        # Fetch loop
        while self.running:
            try:
                response = requests.get(DISCORD_API_URL, timeout=5)
                if response.status_code == 200:
                    self._discord_stats = response.json()
                    print(f"Discord stats updated: {self._discord_stats}")
                response.close()
            except Exception as e:
                print(f"Failed to fetch Discord stats: {e}")
            # Redraw screen with stats
            self._redraw()
            await asyncio.sleep(DISCORD_FETCH_INTERVAL)

    def _redraw(self):
        """Redraw the full screen: background, logo, floating nicks, discord stats."""
        blit(ssd, matriisi_img, 0, 0)
        blit_keyed(ssd, logo_img, self.logo_row, self.logo_col)
        for nick, p in self._floating.items():
            if p["opacity"] < MIN_OPACITY:
                continue
            fg = self._fgcolor_for_opacity(p["opacity"])
            self.wri_floating.setcolor(fg, AlphaColor(BLACK))
            Writer.set_textpos(ssd, int(p["y"]), int(p["x"]))
            self.wri_floating.printstring(nick)
            self.wri_floating.setcolor()
        self._draw_discord_stats()
        self.show(True)

    async def _button_handler(self):
        """Handle button press to toggle Discord stats display."""
        ev_subset = ButtonEvents.get_event_subset(
            {
                "btn_select": [ButAct.PRESS],  # Use SELECT button to toggle
            }
        )
        self._be = ButtonEvents(ev_subset)
        
        while self.running:
            ev = await self._be.get_event()
            if ev and ev.but_name == "btn_select" and ev.action == ButAct.PRESS:
                self._show_discord_stats = not self._show_discord_stats
                print(f"Discord stats display: {self._show_discord_stats}")
                self._redraw()

    def _draw_discord_stats(self):
        """Draw Discord stats in top left corner."""
        if not self._show_discord_stats:
            return
        
        try:
            self.wri_floating.setcolor(WHITE, AlphaColor(BLACK))
            
            if self._discord_stats is None:
                Writer.set_textpos(ssd, 2, 2)
                self.wri_floating.printstring("Connecting WiFi...")
            elif "error" in self._discord_stats:
                Writer.set_textpos(ssd, 2, 2)
                self.wri_floating.printstring("No WiFi")
            else:
                members_online = self._discord_stats.get("membersOnline", 0)
                member_count = self._discord_stats.get("memberCount", 0)
                messages_today = self._discord_stats.get("messagesToday", 0)
                
                # Line 1: "Discord stats:"
                Writer.set_textpos(ssd, 2, 2)
                self.wri_floating.printstring("Discord stats:")
                
                # Line 2: "Members: online / count"
                Writer.set_textpos(ssd, 16, 2)
                self.wri_floating.printstring(f"Members: {members_online}/{member_count}")
                
                # Line 3: "Messages today: xx"
                Writer.set_textpos(ssd, 30, 2)
                self.wri_floating.printstring(f"Messages: {messages_today}")
            
            self.wri_floating.setcolor()
        except Exception as e:
            print(f"Error drawing Discord stats: {e}")

    def _fgcolor_for_opacity(self, opacity):
        if opacity > 0.6:
            return WHITE
        if opacity > 0.2:
            return GREY
        return BLACK

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
                print(f"Beacon from: {nick}, own: {self.nick}, match: {nick == self.nick}")
                if nick == self.nick:
                    continue
                async with self._floating_lock:
                    if nick not in self._floating:
                        print(f"Adding new floating nick: {nick}")
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
                        print(f"Refreshing floating nick: {nick}")
                        self._floating[nick]["opacity"] = 1.0
                        self._floating[nick]["last_seen"] = time()
        except asyncio.CancelledError:
            pass

    async def _nearby_friends_animation(self):
        while self.running:
            await asyncio.sleep(ANIMATION_INTERVAL)
            need_clear = False
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
                floating = list(self._floating.items())
                need_clear = to_remove and not self._floating
            if not floating and not need_clear:
                continue
            self._redraw()

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
