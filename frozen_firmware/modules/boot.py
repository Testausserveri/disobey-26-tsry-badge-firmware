"""
Boot initialization - runs before main.py
Sets up development utilities available in REPL and development
"""

import sys
import gc

def badge_help():
    """Print badge development help and system information"""
    gc.collect()
    
    print("\n" + "="*50)
    print("🔌 Badge Development Environment")
    print("="*50)
    print(f"MicroPython: {sys.version}")
    
    # Try to get version info, but don't crash if files are missing
    try:
        from bdg.version import Version
        print(f"Badge Version: {Version().version}")
        print(f"Badge Build: {Version().build}")
    except (OSError, ImportError):
        print("Badge Version: (development mode - version file not available)")
    
    print(f"\nMemory:")
    print(f"  Free: {gc.mem_free()} bytes")
    print(f"  Allocated: {gc.mem_alloc()} bytes")
    
    print("\n" + "="*50)
    print("Available commands:")
    print("="*50)
    print("  load_app(app_name)     - Load a specific app/game")
    print("  config                 - Access badge configuration")
    print("  badge_help()           - Print this help message")
    print("  gc.collect()           - Force garbage collection")
    print("\nDocumentation:")
    print("  https://github.com/disobeyfi/disobey-badge-2025-game-firmware/blob/main/docs/badge_api.md")
    print("="*50 + "\n")

try:
    from bdg.repl_helpers import load_app
    from bdg.config import Config
    
    # Make these available globally so they're accessible in REPL
    globals()["load_app"] = load_app
    globals()["config"] = Config()
    globals()["badge_help"] = badge_help
    
    print("REPL utilities initialized: load_app, config, badge_help()")
except Exception as e:
    print(f"Error initializing REPL utilities: {e}")
