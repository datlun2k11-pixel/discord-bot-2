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
    return "GenA-Bot is alive! 🚀"

def start_keep_alive():
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=config.PORT),
        daemon=True,
    )
    thread.start()

def shutdown_handler():
    """Lưu data khi bot tắt"""
    print("🔄 Đang lưu dữ liệu...")
    config.save_all_data()
    print("✅ Đã lưu xong!")

# Đăng ký handler
atexit.register(shutdown_handler)

def main():
    start_keep_alive()
    try:
        bot.run(config.DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi bot: {e}")
        config.save_all_data()

if __name__ == "__main__":
    main()