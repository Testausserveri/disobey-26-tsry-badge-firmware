import hardware_setup as hardware_setup
from hardware_setup import BtnConfig, LED_PIN, LED_AMOUNT, LED_ACTIVATE_PIN

from gui.core.colors import GREEN, BLACK, CYAN, YELLOW
from gui.fonts import font10, font14
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import Label
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.version import Version
from bdg.config import Config
import gc


class InfoScreen(Screen):
    """Display firmware version and system information"""

    def __init__(self):
        super().__init__()

        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        self.wri_title = CWriter(ssd, font14, GREEN, BLACK, verbose=False)

        # Title
        Label(self.wri_title, 10, 10, "Badge Info")

        # Get version information
        try:
            version = Version()
            fw_version = version.version
            fw_build = version.build
        except Exception as e:
            fw_version = "Unknown"
            fw_build = "Unknown"
            print(f"Error reading version: {e}")

        # Get config information
        nickname = Config.config.get("espnow", {}).get("nick", "Unknown")
        wifi_ssid = Config.config.get("ota", {}).get("wifi", {}).get("ssid", "Not set")

        # Memory info
        gc.collect()
        mem_free = gc.mem_free()
        mem_alloc = gc.mem_alloc()
        mem_total = mem_free + mem_alloc
        
        # Convert to KB for readability
        mem_free_kb = mem_free // 1024
        mem_total_kb = mem_total // 1024

        # Display information
        y = 45
        Label(self.wri, y, 10, f"Firmware: {fw_version}")
        y += 20
        Label(self.wri, y, 10, f"Build: {fw_build}")
        y += 20
        Label(self.wri, y, 10, f"Nickname: {nickname}")
        y += 20
        Label(self.wri, y, 10, f"WiFi SSID: {wifi_ssid}")
        y += 20
        Label(self.wri, y, 10, f"RAM: {mem_free_kb}/{mem_total_kb} KB")

        HiddenActiveWidget(self.wri)  # Enable closing with button
