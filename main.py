# main.py
import os
import asyncio
from collections import defaultdict, deque
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from flask import Flask
import threading
import base64  # THÊM DÒNG NÀY

# ---------- Cấu hình ----------
TOKEN = os.getenv("DISCORD_TOKEN")
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
    },
    "Google-Gemini-3.1-flash-lite": {
        "id": "gemini-3.1-flash-lite",
        "provider": "google",
        "vision": True
    },
    "Google-Gemini-3.5-flash": {
        "id": "gemini-3.5-flash",
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

[ĐỊNH DẠNG CHATLOG & TAG]
- M sẽ thấy tin nhắn lịch sử format: [UserID: <số_id>, Name: <tên_user>]: <nội dung>
- M được phép tag user bằng cú pháp <@UserID>. Dùng đúng lúc đúng chỗ để cà khịa, nhắc tên hoặc kéo vào drama.
- Nếu thấy ai tag m, rep trực tiếp và có thể tag ngược lại nó nếu cần.

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
    flask_app.run(host='0.0.0.0', port=port, debug=False)

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.message_content = True
# Cho phép bot tag user trong reply (không bị Discord chặn mention tự động)
allowed_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
bot = commands.Bot(command_prefix='!', intents=intents, allowed_mentions=allowed_mentions)

async def process_attachments(attachments, provider):
    """Convert Discord attachments sang format AI hiểu"""
    parts = []
    for att in attachments:
        if att.content_type and att.content_type.startswith('image/'):
            if provider == "groq":
                # Groq/OpenAI format: dùng image_url
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": att.url, "detail": "auto"}
                })
            elif provider == "google":
                # Gemini format: cần tải ảnh về rồi encode base64 (hoặc dùng file_api)
                # Cách đơn giản: dùng image_url qua payload khác, hoặc base64
                async with aiohttp.ClientSession() as session:
                    async with session.get(att.url) as resp:
                        img_data = await resp.read()
                        import base64
                        b64 = base64.b64encode(img_data).decode('utf-8')
                        parts.append({
                            "inline_data": {
                                "mime_type": att.content_type,
                                "data": b64
                            }
                        })
    return parts
    
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
        await message.reply(reply, allowed_mentions=allowed_mentions)
        return
    
    system_text = SYSTEM_PROMPT.format(
        user_id=f"<@{message.author.id}>",
        current_time=datetime.now().strftime("%H:%M %d/%m/%Y")
    )
    
    # Xây dựng payload tin nhắn cho AI theo format yêu cầu
    messages = [{"role": "system", "content": system_text}]
            for msg in history:
        if msg["role"] == "user":
            # Thêm tag [Ảnh] nếu tin nhắn cũ có ảnh để bot không bị ngu người
            tag = " [Đã gửi ảnh]" if msg.get("has_image") else ""
            formatted = f"[UserID: {msg['author_id']}, Name: {msg['author_name']}]: {msg['content']}{tag}"
            messages.append({"role": "user", "content": formatted})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})
            
            # Kiểm tra xem có attachments không
            if msg.get("attachments") and model_config["vision"]:
                # Tái tạo lại attachments
                att_parts = []
                for att in msg["attachments"]:
                    if model_config["provider"] == "groq":
                        att_parts.append({
                            "type": "image_url", 
                            "image_url": {"url": att["url"], "detail": "auto"}
                        })
                    elif model_config["provider"] == "google":
                        async with aiohttp.ClientSession() as session:
                            async with session.get(att["url"]) as resp:
                                img_data = await resp.read()
                                b64 = base64.b64encode(img_data).decode('utf-8')
                                att_parts.append({
                                    "inline_data": {"mime_type": att["type"], "data": b64}
                                })
                
                # Format content với attachments
                if model_config["provider"] == "groq":
                    final_content = [{"type": "text", "text": base_text}] + att_parts
                else:
                    final_content = [{"text": base_text}] + att_parts
                messages.append({"role": "user", "content": final_content})
            else:
                # Không có attachments
                messages.append({"role": "user", "content": base_text})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})
            
    # Tin nhắn hiện tại cũng format luôn
    # Xử lý attachment nếu có
    image_parts = await process_attachments(message.attachments, model_config["provider"])
    
    # Format tin nhắn hiện tại
    base_text = f"[UserID: {message.author.id}, Name: {message.author.name}]: {message.content}"
    if image_parts and model_config["vision"]:
        if model_config["provider"] == "groq":
            current_content = [{"type": "text", "text": base_text}] + image_parts
        else:  # google
            current_content = [{"text": base_text}] + image_parts
    else:
        current_content = base_text
    
    messages.append({"role": "user", "content": current_content})
    
    async with message.channel.typing():
        try:
            model_config = MODELS_CONFIG[CURRENT_MODEL]
            reply_text = await call_ai(messages, CURRENT_MODEL, model_config["provider"])
            
            # Lưu lịch sử có kèm author info
                        # Lưu lịch sử có kèm author info và attachments
                        # Lưu history, bỏ attachments đi cho nhẹ, chỉ lưu flag
            chat_histories[context_id].append({
                "role": "user",
                "content": message.content,
                "author_id": str(message.author.id),
                "author_name": message.author.name,
                "has_image": model_config["vision"] and any(att.content_type and att.content_type.startswith('image/') for att in message.attachments)
            })
            chat_histories[context_id].append({"role": "assistant", "content": reply_text})
            
            await message.reply(reply_text, allowed_mentions=allowed_mentions)
        except Exception as e:
            await message.reply(f"Lỗi rồi m ơi: {str(e)[:100]} 💀", allowed_mentions=allowed_mentions)
    
    await bot.process_commands(message)

# ---------- Autocomplete cho model_id ----------
async def model_id_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    provider = getattr(interaction.namespace, 'provider', None)
    choices = []
    for name, config in MODELS_CONFIG.items():
        if provider and config["provider"] != provider.lower():
            continue
        if current.lower() in name.lower() or current.lower() in config["id"].lower():
            choices.append(app_commands.Choice(name=name, value=name))
        if len(choices) >= 25:
            break
    return choices

# ---------- Slash Commands ----------
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.describe(
    provider="Chọn provider: groq hoặc google",
    model_id="Tên model có sẵn (gõ để search)",
    custom_model_id="ID model riêng (ví dụ: openai/gpt-oss-20b). Ưu tiên hơn model_id"
)
@app_commands.choices(provider=[
    app_commands.Choice(name="Groq", value="groq"),
    app_commands.Choice(name="Google", value="google")
])
@app_commands.autocomplete(model_id=model_id_autocomplete)
async def model_cmd(interaction: discord.Interaction, provider: str = None, model_id: str = None, custom_model_id: str = None):
    global CURRENT_MODEL

    if not provider:
        await interaction.response.send_message("chọn provider rồi đổi bro 🥀", ephemeral=True)
        return

    provider = provider.lower()
    if provider not in ["groq", "google"]:
        await interaction.response.send_message(f"Provider '{provider}' k hợp lệ. Chọn groq hoặc google 💀", ephemeral=True)
        return

    final_model_name = None
    final_model_id = None

    if custom_model_id:
        final_model_name = f"Custom-{custom_model_id}"
        final_model_id = custom_model_id
        if final_model_name not in MODELS_CONFIG:
            MODELS_CONFIG[final_model_name] = {
                "id": custom_model_id,
                "provider": provider,
                "vision": False
            }
    elif model_id:
        if model_id not in MODELS_CONFIG:
            await interaction.response.send_message(f"Model '{model_id}' k có trong list. Thử autocomplete hoặc dùng custom_model_id 🫩", ephemeral=True)
            return
        if MODELS_CONFIG[model_id]["provider"] != provider:
            await interaction.response.send_message(f"Model '{model_id}' thuộc {MODELS_CONFIG[model_id]['provider']}, k phải {provider} ☠️", ephemeral=True)
            return
        final_model_name = model_id
        final_model_id = MODELS_CONFIG[model_id]["id"]
    else:
        available = [f"• `{n}`" for n, c in MODELS_CONFIG.items() if c["provider"] == provider]
        if not available:
            await interaction.response.send_message(f"Provider {provider} rỗng bro 💀", ephemeral=True)
            return
        embed = discord.Embed(title=f"Models có sẵn cho {provider}", color=0x7289da)
        embed.description = "\n".join(available)
        embed.set_footer(text="Gõ model_id để chọn hoặc custom_model_id để nhập riêng")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    CURRENT_MODEL = final_model_name
    await interaction.response.send_message(f"Đã đổi sang model: `{final_model_id}` (provider: {provider}) ✌🏿", ephemeral=False)

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