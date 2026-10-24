"""Loads settings from the local .env file. Never hard-code keys anywhere else.

Owner: Person 3 (Product & Dashboard). Add new variables to .env.example too.
"""

import os

from dotenv import load_dotenv

load_dotenv()


# Returns a required environment variable or raises an error naming what is missing.
def get_required_env(variable_name: str) -> str:
    value = os.getenv(variable_name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing {variable_name}. Copy .env.example to .env and set it."
        )
    return value
