import os
import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config() -> dict:
    app_env = os.getenv("APP_ENV", "dev")

    config_path = f"config/config_{app_env}.yaml"

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config


settings = load_config()