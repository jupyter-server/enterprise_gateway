"""""Utilities to make checking environment variables easier"""
import os


def is_env_true(env_variable_name: str) -> bool:
    """If environment variable is set and value is case-insensitively "true", then return true. Else return false"""
    return bool(os.getenv(env_variable_name, "False").lower() == "true")
