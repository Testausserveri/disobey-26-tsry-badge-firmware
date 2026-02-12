import hardware_setup as hardware_setup
from hardware_setup import BtnConfig, LED_PIN, LED_AMOUNT, LED_ACTIVATE_PIN

from gui.core.colors import GREEN, BLACK, CYAN, YELLOW, MAGENTA
from gui.fonts import font10, font14
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import Label
from bdg.widgets.hidden_active_widget import HiddenActiveWidget


class CreditsScreen(Screen):
    """Display badge team credits"""

    def __init__(self):
        super().__init__()

        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        self.wri_title = CWriter(ssd, font14, CYAN, BLACK, verbose=False)
        self.wri_special = CWriter(ssd, font10, MAGENTA, BLACK, verbose=False)

        # Title
        Label(self.wri_title, 5, 10, "Badge Team")

        # Team members
        team_members = [
            "Annenaattori",
            "Dist",
            "Hasanen",
            "Kriisi",
            "onja",
            "Paaris",
            "Sanduuz",
            "Shadikka",
            "tidely",
            "Troyhy",
            "Zokol",
        ]

        # Display in two columns
        y = 35
        col1_x = 10
        col2_x = 170
        
        for i, member in enumerate(team_members):
            if i % 2 == 0:
                # Left column
                Label(self.wri, y, col1_x, member)
            else:
                # Right column
                Label(self.wri, y, col2_x, member)
                y += 17  # Move to next row after right column (15 + 2px spacing)

        # If odd number of members, adjust y
        if len(team_members) % 2 == 1:
            y += 17

        # PCB Graphics designer
        y += 5
        Label(self.wri_special, y, col1_x, "PCB Graphics:")
        Label(self.wri_special, y, col2_x, "tracy")

        HiddenActiveWidget(self.wri)  # Enable closing with button
