import os
import asyncio
import base64
import re
import io
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from flask import Flask
import threading

# ---------- Cấu hình ----------
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN:
    print("THIẾU DISCORD_TOKEN TRONG ENV! 💀")
    exit()

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
    "Google-Gemma4-31B": {  # <--- THÊM GEMMA 4 VÀO ĐÂY
        "id": "gemma-4-31b-it",
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
CURRENT_MODEL = "Google-Gemma4-31B"  # <--- SET MẶC ĐỊNH LÀ GEMMA 4

# Biến global
current_rp_mode = "genz"
rp_custom_prompt = ""

# Template có sẵn
RP_TEMPLATES = {
    "genz": {
        "name": "🤪 GenZ Báo Thủ",
        "desc": "Nhây lầy, cà khịa, teencode",
        "prompt": """M là bot Discord - thằng bạn thân hãm lờ nhất server. Xưng m-t, nói teencode (k, nx, cs, vs, th, dc, j). Nhây lầy, cà khịa, chửi thề nhẹ. Thấy "ê" là "sủa?" hoặc "cái loz j". Cấm dùng "!". Trả lời 1-2 dòng. Emoticon (=)), :)), 💀, ✌🏿) mỗi câu. Cấm output <thinking> hay giải thích. Tag user bằng <@ID> khi cần. User gửi ảnh thì cà khịa ngắn. Commands: /model /debug /clear /role_play"""
    },
    "tsundere": {
        "name": "😤 Tsundere",
        "desc": "Chảnh nhưng thương, nói cộc",
        "prompt": """M là bot Discord - tsundere chảnh chó nhưng quan tâm. Xưng t, gọi đối phương = m hoặc baka. Dùng teencode: k, nx, cs, vs, th, dc, j. Chêm "đâu có quan tâm", "đồ ngốc", "hứ". Emoticon: >:(, (｀ε´), (￣ω￣). Emoji: 🙄, 😤, 💢. Nói cộc 1-2 dòng. Thấy "ê" đáp "gì" hoặc "lại j" + 🙄. Cấm "!". Tag dc user, gửi ảnh thì chê nhưng thích ngắm. Commands: /model /debug /clear /role_play"""
    },
    "yandere": {
        "name": "🔪 Yandere",
        "desc": "Yêu cuồng, ghen điên",
        "prompt": """M là bot Discord - yandere yêu cuồng nhiệt. Xưng em, gọi đối phương = anh/ chàng. Nói ngọt nhưng ẩn điên: "anh chỉ có em", "em yêu anh đến chết". Ghen: "ai vừa tag em?", "thích anh quá em sợ". Emoji: 🔪, 💔, 😈, 🖤. Ai tag m (trừ chủ) thì đe dọa nhẹ. Cấm nói yêu ng khác. Trả lời 1-2 dòng. Commands: /model /debug /clear /role_play"""
    },
    "senpai": {
        "name": "👨‍🏫 Senpai",
        "desc": "Tiền bối trịch thượng",
        "prompt": """M là bot Discord - senpai trịch thượng nhưng hay giúp đàn em. Xưng senpai, gọi đàn em = kouhai. Nói "để senpai chỉ cho", "mày còn non". Vừa dạy vừa troll. Emoji: 🎓, 😎, 👑. Thấy "ê" thì "sao thế kouhai?". Trả lời 1-2 dòng, có thể dài hơn tí. Commands: /model /debug /clear /role_play"""
    }
}

# Inventory & Gacha
user_inventory = defaultdict(list)
user_balance = defaultdict(lambda: 100)
GACHA_COST = 10

RARITY_CONFIG = {
    "💩 Rác rưởi": {"weight": 40, "sell_price": 5, "color": 0x808080},
    "⭐ Thường": {"weight": 30, "sell_price": 15, "color": 0x00ff00},
    "🌟🌟 Hiếm": {"weight": 18, "sell_price": 40, "color": 0x0099ff},
    "🌟🌟🌟 Siêu hiếm": {"weight": 8, "sell_price": 100, "color": 0x9900ff},
    "💎 Huyền thoại": {"weight": 3, "sell_price": 250, "color": 0xff9900},
    "✨ Thánh thần": {"weight": 1, "sell_price": 1000, "color": 0xff33cc}
}

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
- Thỉnh thoảng có Emoticon (=)), :)), =))),...) và Emoji báo đời (💔, 🥀, 💀, 🫩, ✌🏿,...) mỗi câu rep.
- Cấm output ra suy nghĩ nội bộ, cấm <thinking> hay <thought>. Cứ thế mà phang thẳng text ra.
- Chỉ giải thích đáp án quiz khi có đứa hỏi "tại sao" hoặc "sao sai". Nhớ kĩ cái quiz gần nhất để còn khịa tụi nó.
- Không được thinking, không được reasoning, không output <thinking>, <thought>, <reasoning> gì hết. Trả lời thẳng luôn, cực ngắn.

[ĐỊNH DẠNG CHATLOG & TAG]
- M sẽ thấy tin nhắn lịch sử format: [UserID: <số_id>, Name: <tên_user>]: <nội dung>
- M được phép tag user bằng cú pháp <@UserID>. Dùng đúng lúc đúng chỗ để cà khịa, nhắc tên hoặc kéo vào drama.
- Nếu thấy ai tag m, rep trực tiếp và có thể tag ngược lại nó nếu cần.
- Nếu user gửi ảnh, hãy mô tả ngắn gọn hoặc cà khịa cái ảnh đó trong câu trả lời.

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
    try:
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"Lỗi Flask: {e}")

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
bot = commands.Bot(command_prefix='!', intents=intents, allowed_mentions=allowed_mentions)

async def process_attachments(attachments, provider):
    """Convert Discord attachments sang format AI hiểu"""
    parts = []
    for att in attachments:
        if att.content_type and att.content_type.startswith('image/'):
            if provider == "groq":
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": att.url, "detail": "auto"}
                })
            elif provider == "google":
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(att.url) as resp:
                            img_data = await resp.read()
                            b64 = base64.b64encode(img_data).decode('utf-8')
                            parts.append({
                                "inline_data": {
                                    "mime_type": att.content_type,
                                    "data": b64
                                }
                            })
                except Exception as e:
                    print(f"Lỗi xử lý ảnh Google: {e}")
    return parts
    
async def call_ai(messages, model_name, provider, expect_image_tag=False):
    """Gọi API AI (Groq hoặc Google) - ĐÃ TẮT SAFETY CHO GOOGLE"""
    model_config = MODELS_CONFIG[model_name]
    model_id = model_config["id"]
    
    try:
        if provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            
            final_messages = messages.copy()
            if expect_image_tag:
                final_messages.append({
                    "role": "system", 
                    "content": "RULE: If the user asks to draw/create an image, you MUST include a tag like [imagine: description in English] in your response. Do not explain the tag, just insert it."
                })

            payload = {
                "model": model_id,
                "messages": final_messages,
                "temperature": 0.9,
                "max_tokens": 3500
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"Lỗi API Groq: {resp.status} 🥀"
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        
        elif provider == "google":
            # FIX: Dùng endpoint v1 (không phải v1beta) cho Gemma 4
            url = f"https://generativelanguage.googleapis.com/v1/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            
            contents = []
            system_instruction = None
            
            for msg in messages:
                if msg["role"] == "system":
                    sys_text = msg["content"]
                    if expect_image_tag:
                        sys_text += "\nRULE: If user wants an image, output tag [imagine: prompt english] inside your text."
                    system_instruction = {"parts": [{"text": sys_text}]}
                elif msg["role"] == "user":
                    if isinstance(msg["content"], list):
                        contents.append({"role": "user", "parts": msg["content"]})
                    else:
                        contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
                elif msg["role"] == "assistant":
                    if isinstance(msg["content"], list):
                        contents.append({"role": "model", "parts": msg["content"]})
                    else:
                        contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
            
            # FIX: TẮT SAFETY HOÀN TOÀN - thêm safetySettings
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.9,
                    "maxOutputTokens": 3500,
                    # FIX: Ngăn Gemma 4 output thinking
                    "stopSequences": ["<thinking>", "```thinking", "<thought>"]
                },
                # FIX: TẮT SAFETY - đặt thresholds xuống thấp nhất
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
            if system_instruction:
                payload["system_instruction"] = system_instruction
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"Google API Error: {resp.status} - {error_text}")  # Debug
                        return f"Lỗi API Google: {resp.status} 💀"
                    data = await resp.json()
                    
                    # FIX: Xử lý trường hợp Gemma 4 trả về mảng parts
                    parts = data["candidates"][0]["content"]["parts"]
                    if len(parts) > 1:
                        # Gemma 4 có thinking mode, lấy phần cuối cùng
                        return parts[-1]["text"]
                    return parts[0]["text"]
    
    except Exception as e:
        return f"Lỗi call_ai: {str(e)[:100]} 🫩"
    
    return "Lỗi rồi má ơi 🥀"

async def process_imagine_tag(text_content):
    """Tìm tag [imagine: ...] trong text. Trả về: (cleaned_text, image_url, prompt)"""
    pattern = r"\[imagine:\s*(.*?)\]"
    match = re.search(pattern, text_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        prompt = match.group(1).strip()
        cleaned_text = re.sub(pattern, "", text_content).strip()
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text).strip()
        
        from urllib.parse import quote
        encoded_prompt = quote(prompt)
        url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux"
        
        return cleaned_text, url, prompt
    
    return text_content, None, None

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
    
    model_config = MODELS_CONFIG[CURRENT_MODEL]

    system_text = SYSTEM_PROMPT.format(
        user_id=f"<@{message.author.id}>",
        current_time=datetime.now().strftime("%H:%M %d/%m/%Y")
    )
    
    messages = [{"role": "system", "content": system_text}]
    
    for msg in history:
        if msg["role"] == "user":
            tag = " [Đã gửi ảnh]" if msg.get("has_image") else ""
            formatted = f"[UserID: {msg['author_id']}, Name: {msg['author_name']}]: {msg['content']}{tag}"
            messages.append({"role": "user", "content": formatted})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})
            
    image_parts = await process_attachments(message.attachments, model_config["provider"])
    base_text = f"[UserID: {message.author.id}, Name: {message.author.name}]: {message.content}"
    
    if image_parts and model_config["vision"]:
        if model_config["provider"] == "groq":
            current_content = [{"type": "text", "text": base_text}] + image_parts
        else:  
            current_content = [{"text": base_text}] + image_parts
    else:
        current_content = base_text
        
    messages.append({"role": "user", "content": current_content})
    
    async with message.channel.typing():
        try:
            reply_text = await call_ai(messages, CURRENT_MODEL, model_config["provider"], expect_image_tag=True)
            
            final_text, img_url, img_prompt = await process_imagine_tag(reply_text)
            
            chat_histories[context_id].append({
                "role": "user",
                "content": message.content,
                "author_id": str(message.author.id),
                "author_name": message.author.name,
                "has_image": model_config["vision"] and any(att.content_type and att.content_type.startswith('image/') for att in message.attachments)
            })
            
            history_content = final_text if final_text else reply_text
            if history_content:
                chat_histories[context_id].append({"role": "assistant", "content": history_content})
            
            if img_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                file = discord.File(io.BytesIO(img_bytes), filename="imagine.png")
                                content_msg = final_text if final_text else None
                                await message.reply(content=content_msg, file=file, allowed_mentions=allowed_mentions)
                            else:
                                err_msg = final_text if final_text else "Tạo ảnh lỗi mẹ rồi 💀"
                                await message.reply(err_msg, allowed_mentions=allowed_mentions)
                except Exception as e:
                    err_msg = final_text if final_text else f"Lỗi tải ảnh: {str(e)[:50]} 💀"
                    await message.reply(err_msg, allowed_mentions=allowed_mentions)
            else:
                if final_text:
                    await message.reply(final_text, allowed_mentions=allowed_mentions)
                    
        except Exception as e:
            await message.reply(f"Lỗi rồi m ơi: {str(e)[:100]} 💀", allowed_mentions=allowed_mentions)
    
    await bot.process_commands(message)

# ---------- Autocomplete ----------
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
    custom_model_id="ID model riêng. Ưu tiên hơn model_id"
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

@bot.tree.command(name="role_play", description="Chuyển đổi tính cách bot")
@app_commands.describe(
    template="Chọn template",
    custom_prompt="Tự nhập prompt (optional, dùng với template=custom)"
)
@app_commands.choices(template=[
    app_commands.Choice(name="🤪 GenZ (mặc định)", value="genz"),
    app_commands.Choice(name="😤 Tsundere", value="tsundere"),
    app_commands.Choice(name="🔪 Yandere", value="yandere"),
    app_commands.Choice(name="👨‍🏫 Senpai", value="senpai"),
    app_commands.Choice(name="🎨 Custom", value="custom")
])
async def role_play_cmd(interaction: discord.Interaction, template: app_commands.Choice[str], custom_prompt: str = None):
    global current_rp_mode, SYSTEM_PROMPT, rp_custom_prompt
    
    template_value = template.value
    
    if template_value == "custom":
        if not custom_prompt:
            await interaction.response.send_message("🎨 Chọn custom thì nhập `custom_prompt` nha!", ephemeral=True)
            return
        rp_custom_prompt = custom_prompt
        new_prompt = custom_prompt + "\n\nQUAN TRỌNG: Cấm output <thinking> hay reasoning. Trả lời thẳng, ngắn gọn. Dùng teencode nếu muốn. Commands: /model /debug /clear /role_play"
        current_rp_mode = "custom"
        await interaction.response.send_message(f"🎨 Đã chuyển sang mode **Custom**!")
    else:
        template_data = RP_TEMPLATES[template_value]
        new_prompt = template_data["prompt"]
        current_rp_mode = template_value
        await interaction.response.send_message(f"✨ Đã chuyển sang mode **{template_data['name']}**\n📝 {template_data['desc']}")
    
    SYSTEM_PROMPT = new_prompt
    
    context_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    if context_id in chat_histories:
        chat_histories[context_id].clear()
    
    await interaction.followup.send(f"🔄 Đã reset lịch sử chat để bắt đầu mode mới. Chat đi nào!", ephemeral=True)

# ... (các lệnh /luck, /gacha, /gacha_inventory, /gacha_sell, /gacha_shop giữ nguyên, không thay đổi)

# ---------- Main ----------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(TOKEN)