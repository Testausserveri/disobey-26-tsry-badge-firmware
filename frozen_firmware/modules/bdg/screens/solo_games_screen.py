import asyncio
from bdg.game_registry import get_registry
from gui.core.colors import GREEN, BLACK, D_PINK, color_map
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.fonts import font10, freesans20
from gui.widgets.label import Label
from gui.widgets.listbox import Listbox
from bdg.widgets.hidden_active_widget import HiddenActiveWidget


class SoloGamesScreen(Screen):
    """Screen for selecting solo games and apps"""
    
    def __init__(self):
        super().__init__()
        color_map[FOCUS] = BLACK 
        
        # Title writer with freesans20 font
        wri = CWriter(ssd, freesans20, GREEN, BLACK, verbose=False)
        # Listbox writer with font10 and D_PINK
        wri_pink = CWriter(ssd, font10, D_PINK, BLACK, verbose=False)

        # Title label centered at top
        self.lbl_title = Label(
            wri,
            10,
            2,
            316,
            bdcolor=False,
            justify=Label.CENTRE,
        )
        self.lbl_title.value("Solo Games & Apps")

        # Load solo games from registry
        registry = get_registry()
        self.games = registry.get_solo_games()
        
        print(f"SoloGamesScreen: Found {len(self.games)} solo games")
        for game in self.games:
            print(f"  - {game['title']} (con_id={game['con_id']})")
        
        # Build game list
        self.els = [game["title"] for game in self.games]
        
        # Ensure at least one element
        if not self.els:
            self.els = ["No solo games available"]

        # Listbox
        self.lb = Listbox(
            wri_pink,
            50,
            2,
            elements=self.els,
            dlines=6,
            bdcolor=D_PINK,
            value=1,
            callback=self.lbcb,
            also=Listbox.ON_LEAVE,
            width=316,
        )

        HiddenActiveWidget(wri_pink)  # Quit button

    def lbcb(self, lb):
        """Listbox callback - launch selected solo game"""
        selected = lb.textvalue()
        print(f"SoloGamesScreen: User selected '{selected}'")
        
        # Find game by title
        for game in self.games:
            if game["title"] == selected:
                screen_class = game["screen_class"]
                screen_args = game.get("screen_args", ())
                print(f"  Launching {screen_class.__name__} with args={screen_args}")
                # Solo games get None as connection
                Screen.change(
                    screen_class, 
                    args=(None,) + screen_args, 
                    mode=Screen.STACK
                )
                break
        else:
            print(f"  Warning: Game '{selected}' not found in registry")
