# Badge Game Registry System

## Overview

The badge firmware now uses a dynamic game registry system that automatically discovers and loads games from multiple sources. This eliminates the need to hardcode game lists in multiple places and makes it easy to add new games.

## Architecture

### Key Components

1. **Game Registry** (`bdg/game_registry.py`): Central registry that scans for and manages available games
2. **Game Configuration**: Each game exports a `badge_game_config()` function with metadata
3. **Dynamic Loading**: Games are loaded from:
   - `badge.games` (development folder, mounted via mpremote)
   - `bdg.games` (frozen firmware, compiled into binary)

### Benefits

- **Single source of truth**: Game information defined once in the game module itself
- **Development override**: Development games automatically override frozen versions
- **Stable IDs**: Connection IDs remain constant across firmware updates
- **Easy expansion**: Add new games by creating a module with `badge_game_config()`

## Adding a New Game

### Step 1: Create Your Game Module

Create your game in either:
- `/firmware/badge/games/your_game.py` (for development)
- `/frozen_firmware/modules/bdg/games/your_game.py` (for frozen/production)

### Step 2: Implement the Screen Class

```python
from gui.core.ugui import Screen
from bdg.msg.connection import Connection

class YourGameScreen(Screen):
    def __init__(self, conn: Connection = None):
        super().__init__()
        self.conn = conn
        # Your game initialization...
```

### Step 3: Add Game Configuration

At the end of your game module, add the configuration function:

```python
def badge_game_config():
    """
    Configuration for your game registration.

    Returns:
        dict: Game configuration with required and optional fields
    """
    return {
        # REQUIRED FIELDS
        "con_id": 10,  # Unique ID (must be stable, never change!)
        "title": "Your Game",  # Display name in menus
        "screen_class": YourGameScreen,  # Screen class to instantiate
        
        # OPTIONAL FIELDS
        "screen_args": (),  # Extra args after Connection (e.g., (False,) for mode)
        "multiplayer": True,  # Whether game requires another badge
        "description": "Short description of your game",
    }
```

### Step 4: Register in Package __init__.py

Add your game module name to the package's `__all__` list:

**For development** (`/firmware/badge/games/__init__.py`):
```python
__all__ = ["tictac", "reaction_game", "rps", "your_game"]
```

**For frozen firmware** (`/frozen_firmware/modules/bdg/games/__init__.py`):
```python
__all__ = ["your_game"]
```

### Step 5: Test

The game will automatically be discovered on next boot or REPL restart.

```python
# In REPL, check if game is registered:
from bdg.game_registry import get_registry
registry = get_registry()
print(registry.get_all_games())

# Or reload registry:
from bdg.game_registry import init_game_registry
init_game_registry()
```

## Connection ID Guidelines

### Choosing a Connection ID

- **Must be unique** across all games
- **Must be stable** - never change once assigned
- **Recommended ranges**:
  - 1-99: Core games (shipped with badge)
  - 100-199: Community games
  - 200-255: Experimental/testing

### Currently Used IDs

| ID | Game | Description |
|----|------|-------------|
| 1  | TicTacToe | Classic tic-tac-toe |
| 2  | Reaction Game | Speed reaction challenge |
| 3  | RPSLS | Rock Paper Scissors Lizard Spock |

## Game Configuration Reference

### Required Fields

- **`con_id`** (int): Unique connection identifier
- **`title`** (str): Display name shown in menus and loading screens
- **`screen_class`** (class): The Screen subclass to instantiate

### Optional Fields

- **`screen_args`** (tuple): Additional positional arguments passed after Connection
  - Default: `()`
  - Example: `(False,)` for casual mode flag
  - Connection object is automatically prepended by the framework
  
- **`multiplayer`** (bool): Whether game requires connection to another badge
  - Default: `False`
  - Set to `True` for badge-to-badge games
  
- **`description`** (str): Short description for UI tooltips/help
  - Default: `""`

## How It Works

### Initialization

1. **Boot Time**: `main.py` calls `init_game_registry()`
2. **Scanning**: Registry scans configured module paths:
   - First scans `badge.games` (development)
   - Then scans `bdg.games` (frozen)
3. **Registration**: Each module's `badge_game_config()` is called
4. **Override**: Development games override frozen versions with same `con_id`

### Connection Handling

When a connection is established:

1. Connection object has `con_id` (e.g., from challenge beacon)
2. `new_con_cb()` in `bdg/__init__.py` calls `registry.get_game(con_id)`
3. Game configuration is retrieved
4. Loading screen shows game title
5. Game screen is instantiated with `(conn,) + screen_args`

### Game Selection UI

The `ScannerScreen` (`bdg/screens/scan_screen.py`):

1. Calls `registry.get_multiplayer_games()` for game list
2. Populates listbox with game titles
3. On selection, looks up `con_id` by title
4. Initiates connection with the `con_id`

## Development Workflow

### Live Development

1. Edit game in `/firmware/badge/games/`
2. Mount firmware folder: `make repl_with_firmware_dir`
3. In REPL, reinitialize registry:
   ```python
   from bdg.game_registry import init_game_registry
   init_game_registry()
   ```
4. Test immediately - no firmware rebuild needed!

### Moving to Production

When game is stable:

1. Copy from `/firmware/badge/games/` to `/frozen_firmware/modules/bdg/games/`
2. Add to `/frozen_firmware/modules/bdg/games/__init__.py`
3. Rebuild firmware: `make build_firmware`
4. Game is now compiled into firmware

### Testing Solo Games

For games that don't require a connection:

```python
from bdg.repl_helpers import load_app

# Load your game directly
load_app("badge.games.your_game", "YourGameScreen", args=(None,))
```

## Troubleshooting

### Game Not Appearing

1. Check `__all__` includes your module name
2. Verify `badge_game_config()` function exists
3. Check for import errors: `import badge.games.your_game`
4. Reinitialize registry: `init_game_registry()`

### Wrong Game Loads

1. Verify `con_id` is unique
2. Check if multiple games have same `con_id`
3. Development games override frozen - is this intended?

### Import Errors

Remember the **critical import order**:

```python
import hardware_setup  # MUST be first for GUI games
from gui.core.colors import *
from gui.core.ugui import Screen
# ... other imports
```

## Example: Complete Game Template

```python
"""
Example Badge Game
A template for creating new badge games.
"""

import hardware_setup  # CRITICAL: Import first for GUI
from gui.core.colors import *
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.fonts import font10
from gui.widgets import Label, Button
from bdg.msg.connection import Connection


class ExampleGameScreen(Screen):
    """Example game screen."""
    
    def __init__(self, conn: Connection = None):
        super().__init__()
        self.conn = conn
        
        # Setup writer
        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        
        # Add widgets
        self.title = Label(self.wri, 2, 2, "Example Game")
        
        # If multiplayer, use connection
        if self.conn:
            self.status = Label(self.wri, 20, 2, f"Connected to {self.conn.peer_mac}")
        else:
            self.status = Label(self.wri, 20, 2, "Solo mode")
    
    def on_open(self):
        """Called when screen opens."""
        # Register async tasks if needed
        pass


def badge_game_config():
    """Game configuration for registration."""
    return {
        "con_id": 100,  # Choose unique ID
        "title": "Example Game",
        "screen_class": ExampleGameScreen,
        "screen_args": (),
        "multiplayer": True,  # Set to False for solo games
        "description": "An example game template",
    }
```

## Future Enhancements

Possible future additions to the registry system:

- Game categories (action, puzzle, etc.)
- Difficulty ratings
- Min/max player counts
- Required badge hardware features
- Game icons/thumbnails
- Version compatibility checking
- Dynamic game download from network
