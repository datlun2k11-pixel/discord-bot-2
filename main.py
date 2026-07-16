import asyncio
import signal
import atexit
import threading
import time
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
    """Health check endpoint - kiểm tra cả bot và Flask"""
    bot_status = "running" if not bot.is_closed() else "closed"
    return f"GenA-Bot is alive! 🚀 (Bot: {bot_status})"

@app.route("/health")
def health():
    """Health check chi tiết - kiểm tra cả bot và Flask"""
    bot_status = "running" if not bot.is_closed() else "closed"
    flask_status = "ok"
    
    response_data = {
        "status": "healthy" if bot_status == "running" else "unhealthy",
        "bot": bot_status,
        "flask": flask_status,
        "timestamp": time.time()
    }
    
    return response_data

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

# Flag để ngăn chặn shutdown loop
_shutdown_in_progress = False
_shutdown_event = None  # Event để main() biết khi nào shutdown xong

def shutdown_handler():
    """Lưu data khi bot tắt (được gọi nhiều lần an toàn) - chạy sync, gọi từ atexit"""
    global _shutdown_in_progress
    if _shutdown_in_progress:
        return
    _shutdown_in_progress = True
    print("🔄 Đang lưu dữ liệu (shutdown_handler)...")
    try:
        config.save_all_data()
        save_memory()
        print("✅ Đã lưu xong!")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu dữ liệu: {e}")

# Đăng ký atexit handler (dự phòng khi crash)
atexit.register(shutdown_handler)

async def shutdown(sig_name: str = "SIGNAL"):
    """Graceful shutdown khi nhận SIGTERM/SIGINT (Koyeb deploy mới)"""
    global _shutdown_in_progress
    if _shutdown_in_progress:
        print(f"⚠️ Shutdown đã được gọi rồi, bỏ qua lần thứ {sig_name}")
        return
    _shutdown_in_progress = True
    
    print(f"\n🛑 Nhận tín hiệu {sig_name}, đang dọn dẹp...")
    try:
        config.save_all_data()
        save_memory()
        print("✅ Đã lưu dữ liệu thành công!")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu dữ liệu: {e}")
    
    try:
        await bot.close()
        print("✅ Bot đã ngắt kết nối Discord an toàn!")
    except Exception as e:
        print(f"⚠️ Lỗi khi đóng bot: {e}")
    
    # Báo hiệu cho main() biết shutdown đã xong
    if _shutdown_event:
        _shutdown_event.set()

async def main():
    loop = asyncio.get_running_loop()

    # === BẮT SIGTERM/SIGINT ĐỂ GRACEFUL SHUTDOWN ===
    # Khi Koyeb deploy phiên bản mới, nó gửi SIGTERM → ta đóng bot connect
    # → bot cũ disconnect → Discord cho phép instance mới connect
    for sig in (signal.SIGTERM, signal.SIGINT):
        # Dùng closure+default argument để capture đúng giá trị sig
        def _make_handler(sig_name: str):
            def _callback():
                # Schedule shutdown - không dùng future.result() tránh deadlock
                # vì signal handler chạy trên event loop thread
                asyncio.ensure_future(shutdown(sig_name), loop=loop)
            return _callback

        loop.add_signal_handler(sig, _make_handler(sig.name))

    # Chạy Flask health-check (Koyeb cần endpoint / để biết app còn sống)
    start_keep_alive()

    # Tạo event để chờ shutdown signal
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    try:
        # Dùng bot.start() thay vì bot.run() để không block event loop
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Bot đã bị tắt thủ công (Ctrl+C)")
        # Gọi shutdown thủ công
        await shutdown("Ctrl+C")
    except Exception as e:
        print(f"❌ Lỗi bot: {e}")
        # Ghi log chi tiết hơn
        import traceback
        traceback.print_exc()
        # Cố gắng lưu dữ liệu trước khi thoát
        try:
            config.save_all_data()
            save_memory()
        except:
            pass
    
    # Nếu shutdown signal được gửi, chờ bot đóng xong
    if _shutdown_event:
        await _shutdown_event.wait()

if __name__ == "__main__":
    asyncio.run(main())