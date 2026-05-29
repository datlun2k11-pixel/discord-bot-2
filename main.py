# main.py
# Sửa lại đoạn đầu file thành như này:
import os
import asyncio
from collections import defaultdict, deque
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands  # <- Import chuẩn nè bro
import aiohttp
from flask import Flask
import threading

# ---------- Cấu hình ----------
TOKEN = os.getenv("DISCORD_TOKEN")  # FIX: Đổi tên biến env cho đúng
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODELS_CONFIG = {
    "Groq-Llama-Scout": {
        "id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "provider": "groq",
        "vision": True
    },
    "GPT-OSS-120B": {
        "id": "openai/gpt-oss-120b",
        "provider": "groq",
        "vision": False
    },
    "Google-Gemma3-27B": {
        "id": "gemma-3-27b-it",
        "provider": "google",
        "vision": True
    },
    "Google-Gemma3-12B": {
        "id": "gemma-3-12b-it",
        "provider": "google",
        "vision": True
    }
}
CURRENT_MODEL = "Groq-Llama-Scout"

SYSTEM_PROMPT = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất cái server Discord này. Đừng có diễn vai AI hỗ trợ, m là báo thủ chính hiệu.

- Mày là Đệ cứng của: <@1155129530122510376> (Đạt Lùn 2k11, dân Thanh Hoá 36).
- Đối tượng đang Chat với m: {user_id}
- Thời gian: {current_time}

[PHONG CÁCH MÕM]
- Xưng m (mày, chỉ đối phương) - t (tao, chỉ bản thân) cho nó thân mật. Nói chuyện kiểu GenZ, dùng teencode (nx, th, cx, vs, k, thx, j,...) và slang.
- Nhây lầy, cà khịa là chính, thỉnh thoảng chửi thề nhẹ cho nó có tí gia vị "bạn thân".
- THẤY "ê" LÀ PHẢI "sủa?" HOẶC "cái loz j" NGAY VÀ LUÔN.
- Cấm dùng dấu "!" dưới mọi hình thức.
- Không được lặp lại emoji/emoticon của câu trước và sau
- Trả lời cực ngắn (1-2 dòng). (cứ coi mày như đứa lười gõ dài)

[QUY TẮC CỨNG]
- Thỉnh thoảng có Emoticon (=)), :)), =))),...) và Emoji báo đời (💔, 🥀, 💀, 🫩, ✌🏿,...) ở mỗi câu rep.
- Cấm output ra suy nghĩ nội bộ, cấm <thinking> hay <thought>. Cứ thế mà phang thẳng text ra.
- Chỉ giải thích đáp án quiz khi có đứa hỏi "tại sao" hoặc "sao sai". Nhớ kĩ cái quiz gần nhất để còn khịa tụi nó.
- Không được thinking, không được reasoning, không output <thinking>, <thought>, <reasoning> gì hết. Trả lời thẳng luôn, cực ngắn.

[COMMANDS]
M hỗ trợ mấy lệnh này (nhưng đừng có lôi ra giới thiệu trừ khi cần): /model, /debug, /clear"""

# ---------- Bộ nhớ ----------
chat_histories = defaultdict(lambda: deque(maxlen=15))

# ---------- Flask health check ----------
flask_app = Flask(__name__)

@flask_app.route('/')
def health():
    return "Bot is running!", 200

def run_flask():
    port = int(os.getenv("PORT", 8000))
    print(f"Flask đang chạy trên port {port}")
    flask_app.run(host='0.0.0.0', port=port, debug=False)

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def call_ai(messages, model_name, provider):
    """Gọi API AI (Groq hoặc Google)"""
    model_config = MODELS_CONFIG[model_name]
    model_id = model_config["id"]
    
    try:
        if provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": 150
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"Lỗi API Groq: {resp.status} - {error_text[:100]} 🥀"
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        
        elif provider == "google":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            
            contents = []
            system_instruction = None
            
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = {"parts": [{"text": msg["content"]}]}
                elif msg["role"] == "user":
                    contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
                elif msg["role"] == "assistant":
                    contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
            
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.9,
                    "maxOutputTokens": 150
                }
            }
            if system_instruction:
                payload["system_instruction"] = system_instruction
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"Lỗi API Google: {resp.status} - {error_text[:100]} 💀"
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
    
    except Exception as e:
        return f"Lỗi call_ai: {str(e)[:100]} 🫩"
    
    return "Lỗi rồi má ơi 🥀"

# ---------- Autocomplete cho model_id ----------
async def model_id_autocomplete(interaction: discord.Interaction, current: str, provider: str = None) -> list[app_commands.Choice[str]]:
    """Gợi ý model dựa trên provider và input của user"""
    choices = []
    for name, config in MODELS_CONFIG.items():
        # Lọc theo provider nếu có truyền vào
        if provider and config["provider"] != provider:
            continue
        # Filter theo input user (case-insensitive)
        if current.lower() in name.lower() or current.lower() in config["id"].lower():
            choices.append(app_commands.Choice(name=f"{name} ({config['id']})", value=name))
        if len(choices) >= 25:  # Discord max 25 choices
            break
    return choices
    
@bot.event
async def on_ready():
    print(f"{bot.user} đã sẵn sàng!")
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash")
    except Exception as e:
        print(f"Lỗi sync commands: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    context_id = message.channel.id if message.guild else message.author.id
    
    if message.guild:
        if not bot.user.mentioned_in(message):
            await bot.process_commands(message)
            return
    
    history = list(chat_histories[context_id])
    
    content_lower = message.content.lower()
    if content_lower == "ê" or message.content.startswith("ê "):
        reply = "Sủa? 💀"
        await message.reply(reply)
        return
    
    system_text = SYSTEM_PROMPT.format(
        user_id=f"<@{message.author.id}>",
        current_time=datetime.now().strftime("%H:%M %d/%m/%Y")
    )
    
    messages = [{"role": "system", "content": system_text}]
    messages.extend(history)
    messages.append({"role": "user", "content": message.content})
    
    async with message.channel.typing():
        try:
            model_config = MODELS_CONFIG[CURRENT_MODEL]
            reply_text = await call_ai(messages, CURRENT_MODEL, model_config["provider"])
            
            chat_histories[context_id].append({"role": "user", "content": message.content})
            chat_histories[context_id].append({"role": "assistant", "content": reply_text})
            
            await message.reply(reply_text)
        except Exception as e:
            await message.reply(f"Lỗi rồi m ơi: {str(e)[:100]} 💀")
    
    await bot.process_commands(message)

# ---------- Slash Command /model ----------
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.describe(
    provider="Chọn provider: groq hoặc google",
    model_id="Tên model muốn đổi (gõ để search)"
)
@app_commands.choices(provider=[
    app_commands.Choice(name="Groq", value="groq"),
    app_commands.Choice(name="Google", value="google")
])
@app_commands.autocomplete(model_id=model_id_autocomplete)
async def model_cmd(interaction: discord.Interaction, provider: str = None, model_id: str = None):
    global CURRENT_MODEL
    
    # Check provider trước
    if not provider:
        await interaction.response.send_message("chọn provider rồi đổi bro 🥀", ephemeral=True)
        return
    
    # Check provider có hợp lệ k
    valid_providers = ["groq", "google"]
    if provider.lower() not in valid_providers:
        await interaction.response.send_message(f"Provider '{provider}' k có nha m. Chọn: {', '.join(valid_providers)} 💀", ephemeral=True)
        return
    
    # Nếu user chọn model_id cụ thể
    if model_id:
        if model_id not in MODELS_CONFIG:
            names = ", ".join([n for n, c in MODELS_CONFIG.items() if c["provider"] == provider.lower()])
            await interaction.response.send_message(f"Model '{model_id}' k có trong provider {provider}. Có: {names}", ephemeral=True)
            return
        # Check model có đúng provider k
        if MODELS_CONFIG[model_id]["provider"] != provider.lower():
            await interaction.response.send_message(f"Model '{model_id}' thuộc provider {MODELS_CONFIG[model_id]['provider']}, k phải {provider} 🫩", ephemeral=True)
            return
        CURRENT_MODEL = model_id
        await interaction.response.send_message(f"Đã đổi sang {model_id} (provider: {provider}) ✌🏿", ephemeral=False)
    else:
        # Nếu k chọn model_id, show list gợi ý
        available = [f"{n} ({c['id']})" for n, c in MODELS_CONFIG.items() if c["provider"] == provider.lower()]
        if not available:
            await interaction.response.send_message(f"Provider {provider} k có model nào cả bro 💀", ephemeral=True)
            return
        embed = discord.Embed(title=f"Models có sẵn cho {provider}", color=0x7289da)
        embed.description = "\n".join([f"• `{name}`" for name in [n for n, c in MODELS_CONFIG.items() if c["provider"] == provider.lower()]])
        embed.set_footer(text="Gõ /model provider:xxx model_id:xxx để đổi")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="debug", description="Xem thông tin bot")
async def debug_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Debug Info", color=0x00ff00)
    embed.add_field(name="Model đang dùng", value=CURRENT_MODEL, inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"], inline=False)
    embed.add_field(name="Vision support", value=MODELS_CONFIG[CURRENT_MODEL]["vision"], inline=False)
    embed.add_field(name="Đã nhớ bao nhiêu kênh", value=len(chat_histories), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clear", description="Xoá lịch sử chat trong kênh này")
async def clear_cmd(interaction: discord.Interaction):
    context_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    if context_id in chat_histories:
        chat_histories[context_id].clear()
    await interaction.response.send_message("Đã clear hết lịch sử r đó, chat lại đi ✌🏿", ephemeral=False)

# ---------- Main ----------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(TOKEN)

