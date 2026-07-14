import discord
from discord.ext import commands
import json
import os
import atexit
from flask import Flask
from threading import Thread

def load_json(filepath, default):
    """Load JSON file with error handling."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2)
        return default

def save_json(filepath, data):
    """Save JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Flask keep-alive for Koyeb/Render
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Load config
config = load_json('config.json', {
    'token': '',
    'gemini_api_key': '',
    'default_model': 'gemini-1.5-flash'
})

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Save data on exit
def save_on_exit():
    print("💾 Đang lưu data trước khi tắt...")
    # Save channel memory
    from event import save_channel_memory
    save_channel_memory()

atexit.register(save_on_exit)

async def main():
    # Start Flask in background
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Load extensions
    try:
        from cmd import setup_cmd
        from event import setup_event
        
        await setup_cmd(bot.tree, config)
        await setup_event(bot.tree, config)
    except Exception as e:
        print(f"❌ Lỗi load extensions: {e}")
    
    # Run bot
    await bot.start(config['token'])

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
