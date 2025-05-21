import os

try:
    GAME_TIMEOUT_MINUTES = int(os.getenv("GAME_TIMEOUT_MINUTES", "5"))
except ValueError:
    GAME_TIMEOUT_MINUTES = 5 # Default fallback if env var is not a valid integer
