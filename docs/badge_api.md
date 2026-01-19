# Badge API Documentation

This document describes the API functions available for interacting with the Disobey Badge 2025.

## Table of Contents

- [Global Objects](#global-objects)
  - [`config`](#config)
  - [`load_app`](#load_app)
  - [`badge_help()`](#badge_help)
- [Configuration API](#configuration-api)
  - [WiFi Configuration](#wifi-configuration)
    - [`Config.set_wifi(ssid: str, key: str)`](#configset_wifissid-str-key-str)
  - [Nickname Configuration](#nickname-configuration)
    - [`Config.set_nick(nick: str)`](#configset_nicknick-str)
- [Related Documentation](#related-documentation)

## Global Objects

The badge firmware provides convenient global objects that are automatically available in the REPL:

### `config`

A global `Config` instance that provides access to badge configuration and settings.

**Example:**

```python
>>> config
<Config object at 0x...>
>>> config.config
{'ota': {'host': '...', 'wifi': {'ssid': '...', 'password': '...'}}, 'espnow': {...}}
```

### `load_app()`

A development utility function for loading and testing applications/games.

**Example:**

```python
>>> load_app("badge.options", "OptionScreen", with_espnow=True, with_sta=True)
```

### `badge_help()`

Prints helpful information about the badge development environment, available commands, and system status.

**Features:**
- Displays MicroPython version
- Shows badge firmware version and build info
- Reports memory usage (free and allocated)
- Lists available REPL commands and utilities

**Example:**

```python
>>> badge_help()

==================================================
🔌 Badge Development Environment
==================================================
MicroPython: 3.4.0; MicroPython 78680ea77 on 2026-01-19
Badge Version: (development mode)
Badge Build: abc1234

Memory:
  Free: 8312128 bytes
  Allocated: 9488 bytes

==================================================
Available commands:
==================================================
  load_app(app_name)     - Load a specific app/game
  config                 - Access badge configuration
  badge_help()           - Print this help message
  gc.collect()           - Force garbage collection

Documentation: Check Badge API docs in Github
==================================================
```

This object is automatically created at boot time, so you can use it immediately in the REPL without importing.

## Configuration API

### WiFi Configuration

#### `Config.set_wifi(ssid: str, key: str)`

**Description:**

Set WiFi credentials for OTA updates and network connectivity. Updates the configuration in memory and saves it to `/config.json` for persistence across reboots.

**Parameters:**

- `ssid` (str): WiFi network name (SSID)
- `key` (str): WiFi password/key

**Returns:**

- `None`

**Raises:**

- `OSError`: If unable to save configuration file

**Examples:**

```python
# Import the Config class
from bdg.config import Config

# Load existing configuration first (if not already loaded)
Config.load()

# Set WiFi credentials
Config.set_wifi("MyWiFiNetwork", "MySecurePassword123")
```

**REPL Usage (Method 1 - Using global config object):**

```python
>>> # Use the global config object (already available)
>>> config.set_wifi("DisobeyBadge2026", "disobey2025-badges-moved-permanently")
WiFi config saved: SSID=DisobeyBadge2026
```

**REPL Usage (Method 2 - Using Config class directly):**

```python
>>> from bdg.config import Config
>>> Config.load()
>>> Config.set_wifi("DisobeyBadge2026", "disobey2025-badges-moved-permanently")
WiFi config saved: SSID=DisobeyBadge2026
```

**Notes:**

- Configuration is saved to `/config.json` on the badge's filesystem
- WiFi credentials persist across reboots
- Used by the OTA update system to connect to WiFi
- Call `Config.load()` before `set_wifi()` if config hasn't been loaded yet

**Configuration Structure:**

The function updates the following structure in `/config.json`:

```json
{
  "ota": {
    "host": "https://...",
    "wifi": {
      "ssid": "your-ssid-here",
      "password": "your-password-here"
    }
  },
  "espnow": {
    "ch": 1,
    "beacon": 20,
    "nick": null
  }
}
```

### Nickname Configuration

#### `Config.set_nick(nick: str)`

**Description:**

Set the badge nickname for ESP-NOW communication and badge identification. Validates the nickname and saves it to `/config.json` for persistence across reboots.

**Parameters:**

- `nick` (str): Badge nickname
  - Length: 1-20 characters
  - Allowed characters: ASCII only (no unicode, emojis, or extended characters)

**Returns:**

- `None`

**Raises:**

- `ValueError`: If nickname is empty, exceeds 20 characters, or contains non-ASCII characters
- `OSError`: If unable to save configuration file

**Examples:**

```python
# Import the Config class
from bdg.config import Config

# Load existing configuration first (if not already loaded)
Config.load()

# Set nickname
Config.set_nick("CyberPunk42")
```

**REPL Usage (Method 1 - Using global config object):**

```python
>>> # Use the global config object (already available)
>>> config.set_nick("NeonBlade99")
Nickname saved: NeonBlade99
```

**REPL Usage (Method 2 - Using Config class directly):**

```python
>>> from bdg.config import Config
>>> Config.load()
>>> Config.set_nick("GhostRunner1337")
Nickname saved: GhostRunner1337
```

**Error Handling Examples:**

```python
>>> config.set_nick("")  # Too short
ValueError: Nickname must be at least 1 character

>>> config.set_nick("ThisNicknameIsWayTooLong")  # Too long (>20 chars)
ValueError: Nickname must be 20 characters or less

>>> config.set_nick("Cyber🔥Punk")  # Contains emoji
ValueError: Nickname must contain only ASCII characters
```

**Notes:**

- Configuration is saved to `/config.json` on the badge's filesystem
- Nickname persists across reboots
- Used for ESP-NOW peer-to-peer communication and badge identification
- Call `Config.load()` before `set_nick()` if config hasn't been loaded yet
- If no custom nickname is set, a random cyberpunk-themed nickname is auto-generated at boot

## Related Documentation

- [Game Development Guide](game_development.md) - Create games for the badge
- [Hardware Documentation](../HARDWARE.md) - Badge hardware specifications
- [Development Guide](../DEVELOPMENT.md) - Badge development workflow
