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

config.load_all_data()

bot = commands.Bot(command_prefix="!", intents=config.build_intents())

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
            use_reloader=False,
            threaded=True,
        ),
        daemon=True,
    )
    thread.start()

_shutdown_in_progress = False
_shutdown_done = False

def shutdown_handler():
    """Lưu data khi bot tắt (chạy sync, gọi từ atexit)"""
    global _shutdown_in_progress, _shutdown_done
    if _shutdown_done:
        return
    _shutdown_in_progress = True
    print("🔄 Đang lưu dữ liệu (shutdown_handler)...")
    try:
        config.save_all_data()
        save_memory()
        print("✅ Đã lưu xong!")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu dữ liệu: {e}")
    finally:
        _shutdown_done = True

atexit.register(shutdown_handler)

async def shutdown(sig_name: str = "SIGNAL"):
    """Graceful shutdown khi nhận SIGTERM/SIGINT"""
    global _shutdown_in_progress, _shutdown_done
    if _shutdown_done:
        print(f"⚠️ Shutdown đã hoàn tất, bỏ qua {sig_name}")
        return
    if _shutdown_in_progress:
        print(f"⚠️ Shutdown đang chạy, bỏ qua {sig_name}")
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
    
    _shutdown_done = True

async def main():
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        def _make_handler(sig_name: str):
            def _callback():
                if not _shutdown_done:
                    asyncio.run_coroutine_threadsafe(shutdown(sig_name), loop)
            return _callback

        try:
            loop.add_signal_handler(sig, _make_handler(sig.name))
        except NotImplementedError:
            pass

    start_keep_alive()

    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Bot đã bị tắt thủ công (Ctrl+C)")
        await shutdown("Ctrl+C")
    except Exception as e:
        print(f"❌ Lỗi bot: {e}")
        import traceback
        traceback.print_exc()
        try:
            config.save_all_data()
            save_memory()
        except:
            pass
    finally:
        if not _shutdown_done:
            await shutdown("exit")

if __name__ == "__main__":
    asyncio.run(main())