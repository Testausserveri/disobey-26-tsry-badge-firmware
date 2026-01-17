"""
Dynamic game registry for badge games and apps.

This module provides a centralized registry for games and apps that can be loaded
from either frozen firmware (bdg.games) or development folders (badge.games).

Each game module should export a `badge_game_config()` function that returns a dict with:
- con_id: int - Unique connection ID (must be stable across firmware updates)
- title: str - Display title for menus
- screen_class: class - The Screen subclass to instantiate
- screen_args: tuple - Positional arguments (excluding Connection)
- multiplayer: bool - Whether this is a multiplayer game (requires connection)
- description: str - Optional description for UI
"""

import sys


class GameRegistry:
    """Registry for managing badge games and apps."""

    def __init__(self):
        self._games = {}  # con_id -> game_config
        self._scan_paths = [
            "badge.games",
            "bdg.games",
        ]  # Development first, then frozen

    def scan_games(self):
        """
        Scan configured module paths for games.

        Looks for modules that export a `badge_game_config()` function and
        registers them by their connection ID.
        """
        self._games.clear()

        for path in self._scan_paths:
            try:
                # Try to import the games package
                module = __import__(path, None, None, ["__name__"])

                # Discover submodules dynamically
                submodules = self._discover_submodules(module, path)

                # Try to load each submodule
                for submodule_name in submodules:
                    try:
                        full_path = f"{path}.{submodule_name}"
                        submodule = __import__(full_path, None, None, [submodule_name])

                        # Check if module has the config function
                        if hasattr(submodule, "badge_game_config"):
                            config = submodule.badge_game_config()
                            self.register_game(config, full_path)
                    except Exception as e:
                        print(f"Error loading {path}.{submodule_name}: {e}")

            except ImportError as e:
                # Module path doesn't exist, that's okay
                print(f"Game path {path} not found: {e}")
                pass

    def _discover_submodules(self, module, path):
        """
        Dynamically discover submodules in a package.

        Args:
            module: The imported package module
            path: The module path string (e.g., "badge.games")

        Returns:
            List of submodule names
        """
        import os

        submodules = []

        # Method 1: Check if package defines __all__
        if hasattr(module, "__all__"):
            # Use the explicitly defined list, but verify each has badge_game_config
            for name in module.__all__:
                try:
                    test_module = __import__(f"{path}.{name}", None, None, [name])
                    if hasattr(test_module, "badge_game_config"):
                        submodules.append(name)
                except Exception as e:
                    print(f"Failed to import {path}.{name}: {e}")
            if submodules:
                return submodules

        # Method 2: Try to list files from the module's directory
        try:
            # Get the package's filesystem path
            module_dir = None
            if hasattr(module, "__path__"):
                # For regular packages with __path__
                # In CPython, __path__ is a list; in MicroPython, it's a string
                path_attr = module.__path__
                if isinstance(path_attr, str):
                    module_dir = path_attr
                else:
                    module_dir = path_attr[0]
            elif hasattr(module, "__file__"):
                # Derive directory from __file__
                module_dir = module.__file__.rsplit("/", 1)[0]
            else:
                # Can't determine path, return empty
                return submodules

            # Skip os.listdir for frozen modules (they use virtual .frozen paths)
            if module_dir and module_dir.startswith(".frozen"):
                return submodules

            # List Python files in the directory
            try:
                files = os.listdir(module_dir)
                for filename in files:
                    # Check for .py files, excluding __init__.py
                    if filename.endswith(".py") and filename != "__init__.py":
                        module_name = filename[:-3]  # Remove .py extension

                        # Try to import and check for badge_game_config
                        try:
                            test_module = __import__(
                                f"{path}.{module_name}", None, None, [module_name]
                            )
                            if hasattr(test_module, "badge_game_config"):
                                submodules.append(module_name)
                        except Exception as e:
                            print(f"Failed to import {path}.{module_name}: {e}")
            except OSError:
                # Directory listing not available (frozen modules)
                pass

        except Exception as e:
            print(f"Error discovering submodules in {path}: {e}")

        return submodules

    def register_game(self, config, module_path=None):
        """
        Register a game with the registry.

        Args:
            config: Dict with game configuration (con_id, title, screen_class, etc.)
            module_path: Optional module path for debugging
        """
        con_id = config.get("con_id")
        if con_id is None:
            print(f"Warning: Game config missing con_id: {config}")
            return

        if con_id in self._games:
            existing = self._games[con_id]
            # Allow override from development (badge.games) over frozen (bdg.games)
            existing_path = existing.get("_module_path", "")
            new_path = module_path or ""

            # Prefer badge.games over bdg.games
            if "badge.games" in new_path and "bdg.games" in existing_path:
                print(f"  Game {con_id}: Overriding frozen version with dev version")
                self._games[con_id] = config
                config["_module_path"] = module_path
            elif "badge.games" not in existing_path:
                print(f"  Warning: Game con_id {con_id} already registered")
        else:
            self._games[con_id] = config
            config["_module_path"] = module_path
            print(f"  ✓ {config.get('title')} (ID={con_id}, module={module_path})")

    def get_game(self, con_id):
        """
        Get game configuration by connection ID.

        Args:
            con_id: Connection ID

        Returns:
            Game config dict or None if not found
        """
        return self._games.get(con_id)

    def get_all_games(self):
        """
        Get all registered games.

        Returns:
            List of game config dicts sorted by con_id
        """
        return sorted(self._games.values(), key=lambda g: g.get("con_id", 999))

    def get_multiplayer_games(self):
        """
        Get all multiplayer games (requires connection to another badge).

        Returns:
            List of game config dicts
        """
        return [g for g in self.get_all_games() if g.get("multiplayer", False)]

    def get_solo_games(self):
        """
        Get all solo games (can be played without connection).

        Returns:
            List of game config dicts
        """
        return [g for g in self.get_all_games() if not g.get("multiplayer", False)]


# Global registry instance
_registry = GameRegistry()


def get_registry():
    """Get the global game registry instance."""
    return _registry


def init_game_registry():
    """
    Initialize the game registry by scanning for available games.

    This should be called during badge initialization.
    """
    print("\n=== Initializing Game Registry ===")
    _registry.scan_games()

    # Print summary of found games
    games = _registry.get_all_games()
    print(f"\nFound {len(games)} game(s):")

    solo_games = _registry.get_solo_games()
    multiplayer_games = _registry.get_multiplayer_games()

    if solo_games:
        print(f"\n  Solo games ({len(solo_games)}):")
        for game in solo_games:
            print(f"    - {game.get('title')} (ID={game.get('con_id')})")

    if multiplayer_games:
        print(f"\n  Multiplayer games ({len(multiplayer_games)}):")
        for game in multiplayer_games:
            print(f"    - {game.get('title')} (ID={game.get('con_id')})")

    print("=== Game Registry Ready ===\n")
    return _registry
