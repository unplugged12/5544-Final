"""Entry point for the Esports Mod Copilot Discord bot."""

import logging

from config import Config
from bot import ModBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def main() -> None:
    config = Config.from_env()
    bot = ModBot(config)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
