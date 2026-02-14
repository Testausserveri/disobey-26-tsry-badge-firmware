# Development games package.
# Explicitly list modules so the game registry can discover them
# (avoids relying on os.listdir on mounted filesystem).
__all__ = [
    "flashy",
    "hackergotchi",
    "rps",
    "tetris_solo",
    "testausserveri",
]
