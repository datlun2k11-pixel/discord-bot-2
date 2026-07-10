import threading
from flask import Flask
from discord.ext import commands

import config
from cmd import register_commands
from event import register_events


bot = commands.Bot(command_prefix="/", intents=config.build_intents())

register_commands(bot)
register_events(bot)

app = Flask("")


@app.route("/")
def home():
    return "GenA-Bot is alive!"


def start_keep_alive():
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=config.PORT),
        daemon=True,
    )
    thread.start()


def main():
    start_keep_alive()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
