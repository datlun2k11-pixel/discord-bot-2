import threading
import atexit
from flask import Flask
from discord.ext import commands

import config
from cmd import register_commands
from event import register_events

# Load data khi khởi động
config.load_all_data()

bot = commands.Bot(command_prefix="/", intents=config.build_intents())

register_commands(bot)
register_events(bot)

app = Flask("")

@app.route("/")
def home():
    return "GenA-Bot is alive! \U0001f680"

def start_keep_alive():
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=config.PORT),
        daemon=True,
    )
    thread.start()

def shutdown_handler():
    """Luu data khi bot tat"""
    print("\U0001f504 Dang luu du lieu...")
    config.save_all_data()
    print("\u2705 Da luu xong!")

# Dang ky handler
atexit.register(shutdown_handler)

def main():
    start_keep_alive()
    try:
        bot.run(config.DISCORD_TOKEN)
    except Exception as e:
        print(f"\u274c Loi bot: {e}")
        config.save_all_data()

if __name__ == "__main__":
    main()