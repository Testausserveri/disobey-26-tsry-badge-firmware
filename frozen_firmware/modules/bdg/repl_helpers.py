"""
REPL helper functions for easier development and testing of badge apps and games.
"""

# Global instances for REPL access
_espnow = None
_sta = None
_initialized = False


def _initialize_badge():
    """Initialize badge components if not already initialized"""
    global _espnow, _sta, _initialized

    if _initialized:
        return _espnow, _sta

    import aioespnow
    import network
    from bdg.config import Config
    from hardware_setup import BtnConfig
    from bdg.asyncbutton import ButtonEvents
    from gui.core.ugui import quiet

    print("Initializing badge for REPL...")

    # Init button event machine
    ButtonEvents.init(BtnConfig)

    Config.load()
    channel = int(Config.config["espnow"]["ch"])

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.config(channel=channel)
    sta.config(txpower=10)

    e = aioespnow.AIOESPNow()
    e.active(True)

    own_mac = sta.config("mac")
    print(f"MAC: {own_mac}")

    quiet()

    _espnow = e
    _sta = sta
    _initialized = True

    print("Badge initialized!")
    return e, sta


def set_globals(espnow, sta, Screen=None):
    """Set global espnow, sta instances - called by badge.main if badge starts normally"""
    global _espnow, _sta, _initialized
    _espnow = espnow
    _sta = sta
    _initialized = True


def load_app(
    import_path,
    class_name=None,
    with_espnow=False,
    with_sta=False,
    args=None,
    kwargs=None,
    mode=None,
):
    """
    Load and display an app/game screen for testing in REPL.

    Usage examples:
        load_app("badge.games.reaction_game", "ReactionGameScr", args=(None, True))
        load_app("badge.games.tictac", "TicTacToe", args=(None,))
        load_app("bdg.screens.ota", "OTAScreen", with_espnow=True, with_sta=True, kwargs={"fw_version": "1.0.0", "ota_config": Config.config["ota"]})

    Args:
        import_path: Module path like "badge.games.reaction_game" or "bdg.games.something"
        class_name: Name of the screen class (if None, tries to infer from module)
        with_espnow: Whether to prepend espnow instance to args
        with_sta: Whether to prepend sta instance to args
        args: Additional positional arguments as tuple
        kwargs: Additional keyword arguments as dict
        mode: Screen mode (Screen.STACK, Screen.REPLACE, or Screen.MODAL)
    """
    # Initialize badge if needed
    espnow, sta = _initialize_badge()

    # Import Screen class (safe now after initialization)
    from gui.core.ugui import Screen, ssd

    # Clear/reset display for clean state
    ssd.fill(0)
    ssd.show()

    # Set default mode if not provided
    if mode is None:
        mode = Screen.STACK

    # Import the module dynamically
    parts = import_path.split(".")
    module = __import__(import_path, None, None, [parts[-1]])

    # Get the screen class
    if class_name:
        screen_class = getattr(module, class_name)
    else:
        # Try to find a Screen subclass in the module
        screen_class = None
        for name in dir(module):
            obj = getattr(module, name)
            try:
                if isinstance(obj, type) and issubclass(obj, Screen) and obj != Screen:
                    screen_class = obj
                    print(f"Auto-detected screen class: {name}")
                    break
            except TypeError:
                continue

        if not screen_class:
            raise ValueError(
                f"No Screen class found in {import_path}. Please specify class_name parameter."
            )

    # Build arguments
    final_args = args or ()
    final_kwargs = kwargs or {}

    if with_espnow:
        final_kwargs["espnow"] = espnow

    if with_sta:
        final_kwargs["sta"] = sta

    # Change to the screen
    print(f"Loading {screen_class.__name__} from {import_path}")
    Screen.change(screen_class, mode=mode, args=final_args, kwargs=final_kwargs)
