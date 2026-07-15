import asyncio
import signal
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
    """Chạy Flask health-check endpoint cho Koyeb"""
    import threading
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

# Đăng ký atexit handler (dự phòng)
atexit.register(shutdown_handler)

async def shutdown():
    """Graceful shutdown khi nhận SIGTERM/SIGINT (Koyeb deploy mới)"""
    print("\n🛑 Nhận tín hiệu tắt máy, đang dọn dẹp...")
    config.save_all_data()
    await bot.close()
    print("✅ Bot đã ngắt kết nối Discord an toàn!")

async def main():
    loop = asyncio.get_running_loop()
    
    # === BẮT SIGTERM/SIGINT ĐỂ GRACEFUL SHUTDOWN ===
    # Khi Koyeb deploy phiên bản mới, nó gửi SIGTERM → ta đóng bot.connect
    # → bot cũ disconnect → Discord cho phép instance mới connect
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    # Chạy Flask health-check (Koyeb cần endpoint / để biết app còn sống)
    start_keep_alive()
    
    try:
        # Dùng bot.start() thay vì bot.run() để không block event loop
        await bot.start(config.DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi bot: {e}")
        config.save_all_data()

if __name__ == "__main__":
    asyncio.run(main())