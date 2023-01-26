import os


def is_env_true(env_variable_name: str):
    return bool(os.getenv(env_variable_name, "False").lower() == "true")