import asyncio
import signal
import atexit
import threading
from flask import Flask
from discord.ext import commands

import config
from cmd import register_commands
from event import register_events, save_memory

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
    thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=config.PORT,
            use_reloader=False,  # Tắt hot-reload để tránh memory leak
            threaded=True,       # Xử lý nhiều request cùng lúc
        ),
        daemon=True,
    )
    thread.start()

def shutdown_handler():
    """Lưu data khi bot tắt"""
    print("🔄 Đang lưu dữ liệu...")
    config.save_all_data()
    save_memory()
    print("✅ Đã lưu xong!")

# Đăng ký atexit handler (dự phòng khi crash)
atexit.register(shutdown_handler)

async def shutdown(sig_name: str = "SIGNAL"):
    """Graceful shutdown khi nhận SIGTERM/SIGINT (Koyeb deploy mới)"""
    print(f"\n🛑 Nhận tín hiệu {sig_name}, đang dọn dẹp...")
    config.save_all_data()
    save_memory()
    await bot.close()
    print("✅ Bot đã ngắt kết nối Discord an toàn!")

async def main():
    loop = asyncio.get_running_loop()

    # === BẮT SIGTERM/SIGINT ĐỂ GRACEFUL SHUTDOWN ===
    # Khi Koyeb deploy phiên bản mới, nó gửi SIGTERM → ta đóng bot connect
    # → bot cũ disconnect → Discord cho phép instance mới connect
    for sig in (signal.SIGTERM, signal.SIGINT):
        # Dùng closure+default argument để capture đúng giá trị sig
        def _make_handler(sig_name: str):
            def _callback():
                future = asyncio.run_coroutine_threadsafe(
                    shutdown(sig_name), loop
                )
            return _callback

        loop.add_signal_handler(sig, _make_handler(sig.name))

    # Chạy Flask health-check (Koyeb cần endpoint / để biết app còn sống)
    start_keep_alive()

    try:
        # Dùng bot.start() thay vì bot.run() để không block event loop
        await bot.start(config.DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi bot: {e}")
        config.save_all_data()
        save_memory()

if __name__ == "__main__":
    asyncio.run(main())