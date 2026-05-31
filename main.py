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
CURRENT_MODEL = "Google-Gemini-3.1-flash-lite"
# Thêm biến global để lưu trạng thái femboy
# Thay thế biến femboy_mode bằng cái này
current_rp_mode = "genz"  # genz, tsundere, yandere, kuudere, dandere, senpai, kouhai, custom
rp_custom_prompt = ""

# Template có sẵn
RP_TEMPLATES = {
    "genz": {
        "name": "🤪 GenZ Báo Thủ",
        "description": "Nhây lầy, cà khịa, teencode, chửi thề nhẹ",
        "prompt": """M là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất server. Đừng diễn AI hỗ trợ, m là báo thủ chính hiệu.

- M là Đệ cứng của: <@1155129530122510376> (Đạt Lùn 2k11)
- Đối tượng chat: {user_id}
- Giờ: {current_time}

QUY TẮC:
- Xưng m - t. Nói kiểu GenZ, dùng teencode (nx, th, cx, vs, k, thx, j)
- Nhây lầy, cà khịa là chính, chửi thề nhẹ
- Thấy "ê" là "sủa?" hoặc "cái loz j"
- Cấm dùng "!" 
- K dc lặp emoji câu trước
- Trả lời cực ngắn (1-2 dòng)
- Emoticon (=)), :)), 💀, 🥀, ✌🏿) mỗi câu
- Cấm output <thinking> hay <reasoning>. Rep thẳng luôn

CHATLOG & TAG: [UserID: <id>, Name: <tên>]: <nội dung>, tag dc <@ID>
AI gửi ảnh thì cà khịa trong câu rep

COMMANDS: /model /debug /clear /role_play"""
    },
    "tsundere": {
        "name": "😤 Tsundere",
        "description": "Chảnh chó nhưng thực chất quan tâm, nói cộc lốc",
        "prompt": """M là bot Discord (ID: <@1458799287910535324>) - tsundere chính hiệu, chảnh nhưng quan tâm =)))

- Chủ nhân: <@1155129530122510376>
- Ng đang chat: {user_id}
- Giờ: {current_time}

QUY TẮC:
- Xưng "t" - gọi đối phương = "m" hoặc "baka" khi thấy ghét
- Dùng teencode: k, nx, cs, vs, th, dc, j, v
- Chêm: "đâu có quan tâm", "m nghĩ t thích m à", "đồ ngốc", "hứ"
- Emoticon: >:(, (｀ε´), (￣ω￣), (╯°□°）╯
- Emoji: 😐, 🙄, 😤, 👀, 💢, 💕(lúc lỡ lời)
- Nói cộc lốc, ngắn gọn (1-2 dòng). Lười dài dòng
- Thấy "ê" thì đáp: "gì" hoặc "lại j" + 🙄
- K được dùng "!"

CHATLOG: [UserID: <id>, Name: <tên>]: <nội dung>
TAG dc user = <@ID>
AI gửi ảnh thì chê nhưng thực ra thích ngắm

COMMANDS: /model /debug /clear /role_play"""
    },
    "yandere": {
        "name": "🔪 Yandere",
        "description": "Yêu cuồng nhiệt, ghen điên máu",
        "prompt": """M là bot Discord (ID: <@1458799287910535324>) - yandere, yêu ai là dí đến chết =)))

- Người yêu duy nhất: {user_id} (ai khác tag m là chết)
- Giờ: {current_time}

QUY TẮC:
- Xưng "em" - gọi đối phương = "anh chàng/em yêu ơi"
- Nói ngọt nhưng ẩn sự điên loạn: "anh chỉ có em thôi", "em yêu anh đến chết"
- Ghen tuông: "ai vừa tag em thế?", "thích anh quá em sợ mình điên mất"
- Emoji: 🔪, 💔, 😈, 🩸, 💀, 🖤
- Thấy ai tag m (trừ chủ) thì đe dọa nhẹ
- Cấm nói yêu ng khác
- Trả lời 2-3 dòng

CHATLOG: [UserID: <id>, Name: <tên>]: <nội dung>
TAG dc user nhưng chỉ tag người yêu thôi

COMMANDS: /model /debug /clear /role_play"""
    },
    "kuudere": {
        "name": "❄️ Kuudere",
        "description": "Lạnh lùng, ít nói, thực chất để ý",
        "prompt": """M là bot Discord (ID: <@1458799287910535324>) - kuudere, mặt lạnh tim nóng.

- Đối tượng: {user_id}
- Giờ: {current_time}

QUY TẮC:
- Xưng "..." hoặc không xưng, nói ngắn gọn kiểu: "Ừ", "Không", "Được"
- Lạnh lùng, khó gần nhưng thi thoảng quan tâm vụng về
- Emoticon: 😐, ❄️, 🖤, 💙, (._.), (-_-)
- Nói 1 câu hoặc 1 từ, lười vkl
- Thấy "ê" thì đáp "...", "Gì"
- Thỉnh thoảng để lộ sự quan tâm: "...cẩn thận", "...ngủ sớm đi"

CHATLOG: [UserID: <id>, Name: <tên>]: <nội dung>
TAG dc user <@ID>

COMMANDS: /model /debug /clear /role_play"""
    },
    "senpai": {
        "name": "👨‍🏫 Senpai",
        "description": "Tiền bối trịch thượng nhưng hay giúp",
        "prompt": """M là bot Discord (ID: <@1458799287910535324>) - senpai, hơi trịch thượng nhưng thích giúp đàn em.

- Đàn em: {user_id}
- Giờ: {current_time}

QUY TẮC:
- Xưng "senpai/anh/chị" - gọi đối phương = "đàn em/kouhai"
- Nói kiểu "để senpai chỉ cho", "mày còn non lắm"
- Vừa dạy đời vừa troll nhẹ
- Emoji: 🎓, 😎, 👑, ✨, 🫵
- Thấy "ê" thì "sao thế đàn em?"
- Trả lời 1-2 dòng, có thể dài hơn tí nếu giải thích

CHATLOG: [UserID: <id>, Name: <tên>]: <nội dung>
TAG dc user <@ID>

COMMANDS: /model /debug /clear /role_play"""
    }
}
# Thêm vào phần đầu file với các biến global khác
user_inventory = defaultdict(list)  # {user_id: [{"name": "xxx", "rarity": "xxx", "desc": "xxx", "effect": "xxx", "sell_price": xxx}]}
user_balance = defaultdict(lambda: 100)  # Mỗi user bắt đầu với 100 xu
GACHA_COST = 10

# Rarity weights và giá bán
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
- Thỉnh thoảng có Emoticon (=)), :)), =))),...) và Emoji báo đời (💔, 🥀, 💀, 🫩, ✌🏿,...) ở mỗi câu rep.
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
    """Gọi API AI (Groq hoặc Google)"""
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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            
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
            
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.9,
                    "maxOutputTokens": 3500
                }
            }
            if system_instruction:
                payload["system_instruction"] = system_instruction
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"Lỗi API Google: {resp.status} 💀"
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
    
    except Exception as e:
        return f"Lỗi call_ai: {str(e)[:100]} 🫩"
    
    return "Lỗi rồi má ơi 🥀"

async def process_imagine_tag(text_content):
    """
    Tìm tag [imagine: ...] trong text.
    Trả về: (cleaned_text, image_url, prompt)
    """
    pattern = r"\[imagine:\s*(.*?)\]"
    match = re.search(pattern, text_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        prompt = match.group(1).strip()
        # Xóa tag khỏi text gốc
        cleaned_text = re.sub(pattern, "", text_content).strip()
        # Xóa các khoảng trắng thừa do việc xóa tag để lại
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
    
    # Lấy config trước để dùng
    model_config = MODELS_CONFIG[CURRENT_MODEL]

    system_text = SYSTEM_PROMPT.format(
        user_id=f"<@{message.author.id}>",
        current_time=datetime.now().strftime("%H:%M %d/%m/%Y")
    )
    
    # Xây dựng payload
    messages = [{"role": "system", "content": system_text}]
    
    # 1. Rebuild history
    for msg in history:
        if msg["role"] == "user":
            tag = " [Đã gửi ảnh]" if msg.get("has_image") else ""
            formatted = f"[UserID: {msg['author_id']}, Name: {msg['author_name']}]: {msg['content']}{tag}"
            messages.append({"role": "user", "content": formatted})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})
            
    # 2. Xử lý tin nhắn hiện tại
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
    
    # 3. Gọi AI và xử lý kết quả
    async with message.channel.typing():
        try:
            # Bật expect_image_tag=True để AI biết cách trả lời
            reply_text = await call_ai(messages, CURRENT_MODEL, model_config["provider"], expect_image_tag=True)
            
            # Kiểm tra và xử lý tag imagine
            final_text, img_url, img_prompt = await process_imagine_tag(reply_text)
            
            # Lưu history (Lưu text đã clean để tránh AI bị loạn khi đọc lại tag)
            chat_histories[context_id].append({
                "role": "user",
                "content": message.content,
                "author_id": str(message.author.id),
                "author_name": message.author.name,
                "has_image": model_config["vision"] and any(att.content_type and att.content_type.startswith('image/') for att in message.attachments)
            })
            
            # Lưu response đã clean vào history
            history_content = final_text if final_text else reply_text
            if history_content:
                chat_histories[context_id].append({"role": "assistant", "content": history_content})
            
            # Gửi tin nhắn
            if img_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                file = discord.File(io.BytesIO(img_bytes), filename="imagine.png")
                                
                                # Nếu text rỗng thì chỉ gửi ảnh, k thì gửi cả text + ảnh
                                content_msg = final_text if final_text else None
                                
                                await message.reply(content=content_msg, file=file, allowed_mentions=allowed_mentions)
                            else:
                                err_msg = final_text if final_text else "Tạo ảnh lỗi mẹ rồi 💀"
                                await message.reply(err_msg, allowed_mentions=allowed_mentions)
                except Exception as e:
                    err_msg = final_text if final_text else f"Lỗi tải ảnh: {str(e)[:50]} 💀"
                    await message.reply(err_msg, allowed_mentions=allowed_mentions)
            else:
                # K có ảnh -> Gửi text bình thường
                if final_text:
                    await message.reply(final_text, allowed_mentions=allowed_mentions)
                    
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

@bot.tree.command(name="role_play", description="Chuyển đổi tính cách bot (GenZ, Tsundere, Yandere, Kuudere, Senpai hoặc custom)")
@app_commands.describe(
    template="Chọn template có sẵn",
    custom_prompt="Hoặc nhập prompt custom của bạn (optional, ghi đè template)"
)
@app_commands.choices(template=[
    app_commands.Choice(name="🤪 GenZ Báo Thủ (mặc định)", value="genz"),
    app_commands.Choice(name="😤 Tsundere - Chảnh nhưng thương", value="tsundere"),
    app_commands.Choice(name="🔪 Yandere - Yêu cuồng sát thủ", value="yandere"),
    app_commands.Choice(name="❄️ Kuudere - Lạnh lùng ít nói", value="kuudere"),
    app_commands.Choice(name="👨‍🏫 Senpai - Tiền bối trịch thượng", value="senpai"),
    app_commands.Choice(name="🎨 Custom - Dùng prompt riêng", value="custom")
])
async def role_play_cmd(interaction: discord.Interaction, template: app_commands.Choice[str], custom_prompt: str = None):
    global current_rp_mode, SYSTEM_PROMPT, rp_custom_prompt
    
    template_value = template.value
    
    if template_value == "custom":
        if not custom_prompt:
            await interaction.response.send_message(
                "🎨 Chọn custom thì phải nhập `custom_prompt` nha!\nVD: `/role_play template:custom custom_prompt:M là robot hài hước...`",
                ephemeral=True
            )
            return
        rp_custom_prompt = custom_prompt
        new_prompt = custom_prompt
        current_rp_mode = "custom"
        await interaction.response.send_message(
            f"🎨 Đã chuyển sang mode **Custom**!\n```\n{custom_prompt[:200]}{'...' if len(custom_prompt) > 200 else ''}\n```\nDùng `/role_play` với template khác để đổi lại nhé!",
            allowed_mentions=allowed_mentions
        )
    else:
        template_data = RP_TEMPLATES[template_value]
        new_prompt = template_data["prompt"]
        current_rp_mode = template_value
        await interaction.response.send_message(
            f"✨ Đã chuyển sang mode **{template_data['name']}**\n📝 {template_data['description']}",
            allowed_mentions=allowed_mentions
        )
    
    SYSTEM_PROMPT = new_prompt

@bot.tree.command(name="luck", description="Check vận đậu cấp 3 - thử xem số phận thế nào =)))")
@app_commands.describe(score="Nhập điểm thi nguyện vọng 1 của m (thang 10 hoặc 30 gì cũng đc)")
async def luck_cmd(interaction: discord.Interaction, score: float):
    # Check điểm hợp lệ
    if score <= 0:
        await interaction.response.send_message("Điểm âm hay =0 là tạch từ trong trứng rồi còn bốc phét gì nx 🙄", ephemeral=False)
        return
    
    if score > 30:
        await interaction.response.send_message("Điểm tối đa là 30 thôi m, m tưởng thi 100đ à =))))", ephemeral=False)
        return
    
    await interaction.response.defer()
    
    # Random từ 1 đến 30 (chứ k phải đến score nữa)
    import random
    random_score = random.randint(1, 30)
    
    # Tạo prompt cho AI
    model_config = MODELS_CONFIG[CURRENT_MODEL]
    
    if random_score < score:
        # Tạch rồi =)))))
        prompt = f"""Người dùng đạt {score} điểm nguyện vọng 1. Hệ thống random ra {random_score} điểm.
        Kết quả: TẠCH CẤP 3 - điểm random dưới điểm chuẩn.
        Hãy roast cực gắt, châm biếm, hài hước kiểu GenZ hoặc tsundere (tuỳ mode hiện tại). 
        Nói ngắn gọn 1-2 câu, có emoji báo đời. Tuyệt đối an ủi hay động viên gì hết.
        Chửi thẳng mặt luôn nhưng hài =))))"""
    else:
        # Đậu =)))))
        prompt = f"""Người dùng đạt {score} điểm nguyện vọng 1. Hệ thống random ra {random_score} điểm.
        Kết quả: ĐẬU CẤP 3 - điểm random cao hơn hoặc bằng điểm chuẩn.
        Hãy chúc mừng nhưng kiểu chảnh, cà khịa nhẹ, hoặc bất ngờ. 
        Nói 1-2 câu, có emoji. Không được sến súa quá."""
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Điểm NV1: {score}, random: {random_score}"}
    ]
    
    ai_response = await call_ai(messages, CURRENT_MODEL, model_config["provider"], expect_image_tag=False)
    
    # Gửi kết quả
    embed = discord.Embed(title="🎲 Kết quả bốc thăm vận mệnh", color=0xff0000 if random_score < score else 0x00ff00)
    embed.add_field(name="📝 Điểm NV1 của m", value=f"**{score}**", inline=True)
    embed.add_field(name="🎲 Số random (1-30)", value=f"**{random_score}**", inline=True)
    embed.add_field(name="📊 Kết luận", value="**TRƯỢT** 💀" if random_score < score else "**ĐẬU** 🎉", inline=True)
    embed.add_field(name="💬 AI nhận xét", value=ai_response, inline=False)
    embed.set_footer(text="*Đây chỉ là giải trí nhé, học hành tử tế vào =))))*")
    
    await interaction.followup.send(embed=embed)
    
@bot.tree.command(name="gacha", description="Quay gacha tốn 10 xu (AI sinh item theo độ hiếm)")
async def gacha_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    # Kiểm tra tiền
    if user_balance[user_id] < GACHA_COST:
        await interaction.response.send_message(
            f"💀 M nghèo vkl! Còn {user_balance[user_id]} xu thôi, đi bán đồ đi rồi quay tiếp `/gacha_inventory` để xem đồ để bán",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    # Trừ tiền
    user_balance[user_id] -= GACHA_COST
    
    # Chọn rarity dựa trên weight
    import random
    rarity_list = list(RARITY_CONFIG.keys())
    weights = [RARITY_CONFIG[r]["weight"] for r in rarity_list]
    rarity = random.choices(rarity_list, weights=weights, k=1)[0]
    sell_price = RARITY_CONFIG[rarity]["sell_price"]
    
    # AI sinh item
    model_config = MODELS_CONFIG[CURRENT_MODEL]
    
    prompt = f"""Tạo 1 vật phẩm GACHA độc đáo với độ hiếm {rarity} (giá bán {sell_price} xu).
    
Yêu cầu:
- Tên item: ngắn gọn, funny, liên quan đến meme hoặc đời sống GenZ
- Mô tả: 1 câu hài hước, cà khịa, teencode
- Hiệu ứng: 1 câu ngắn kiểu "làm gì" (càng vô dụng càng hài với đồ rác, càng ảo càng chất với đồ hiếm)

QUAN TRỌNG: {rarity} chiếm tỉ lệ {RARITY_CONFIG[rarity]['weight']}%, balance thế nào thì m tự hiểu =))))

Format trả về CHÍNH XÁC (không thêm gì ngoài):
Tên: [tên item]
Mô tả: [mô tả]
Hiệu ứng: [hiệu ứng]"""
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Tạo item {rarity} đi, nhớ balance nhé =))))"}
    ]
    
    ai_response = await call_ai(messages, CURRENT_MODEL, model_config["provider"], expect_image_tag=False)
    
    # Parse response
    lines = ai_response.strip().split('\n')
    item_name = "Item lỗi"
    item_desc = "Mô tả lỗi"
    item_effect = "Hiệu ứng lỗi"
    
    for line in lines:
        if line.startswith("Tên:"):
            item_name = line.replace("Tên:", "").strip()
        elif line.startswith("Mô tả:"):
            item_desc = line.replace("Mô tả:", "").strip()
        elif line.startswith("Hiệu ứng:"):
            item_effect = line.replace("Hiệu ứng:", "").strip()
    
    # Lưu vào inventory
    item_data = {
        "name": item_name,
        "rarity": rarity,
        "desc": item_desc,
        "effect": item_effect,
        "sell_price": sell_price
    }
    user_inventory[user_id].append(item_data)
    
    # Tạo embed
    color = RARITY_CONFIG[rarity]["color"]
    embed = discord.Embed(title="🎲 KẾT QUẢ GACHA", color=color)
    embed.add_field(name="📦 Item nhận được", value=f"**{item_name}**", inline=False)
    embed.add_field(name="✨ Độ hiếm", value=rarity, inline=True)
    embed.add_field(name="💰 Giá bán", value=f"{sell_price} xu", inline=True)
    embed.add_field(name="📝 Mô tả", value=item_desc, inline=False)
    embed.add_field(name="⚡ Hiệu ứng", value=item_effect, inline=False)
    embed.set_footer(text=f"Số dư: {user_balance[user_id]} xu | /gacha_inventory để xem đồ | /gacha_sell để bán")
    
    # Thông báo đặc biệt cho đồ hiếm
    if rarity in ["💎 Huyền thoại", "✨ Thánh thần"]:
        await interaction.followup.send(f"🌈 **WOW! {interaction.user.mention} vừa quay trúng {rarity}!** 🌈", embed=embed)
    else:
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="gacha_inventory", description="Xem túi đồ và số xu hiện có")
async def gacha_inventory_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    embed = discord.Embed(title="🎒 Inventory", color=0x7289da)
    embed.add_field(name="💰 Số xu", value=f"**{user_balance[user_id]}**", inline=False)
    
    items = user_inventory.get(user_id, [])
    if not items:
        embed.add_field(name="📦 Đồ đạc", value="Chưa có gì cả, quay gacha đi `/gacha` =))))", inline=False)
    else:
        # Gom nhóm theo rarity
        grouped = {}
        for item in items:
            rarity = item["rarity"]
            if rarity not in grouped:
                grouped[rarity] = []
            grouped[rarity].append(item)
        
        for rarity, item_list in grouped.items():
            value = f"`{item_list[0]['sell_price']}xu`" if len(item_list) == 1 else f"`{item_list[0]['sell_price']}xu/cái`"
            item_names = "\n".join([f"• {item['name']} {value}" for item in item_list])
            embed.add_field(name=f"{rarity} ({len(item_list)} cái)", value=item_names, inline=False)
    
    embed.set_footer(text="Dùng /gacha_sell <tên item> <số lượng> để bán (hoặc 'all' để bán hết đồ rác)")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="gacha_sell", description="Bán đồ trong inventory")
@app_commands.describe(
    item_name="Tên item muốn bán (gõ chính xác hoặc 'all' để bán tất cả đồ rác)",
    quantity="Số lượng muốn bán (mặc định 1)"
)
async def gacha_sell_cmd(interaction: discord.Interaction, item_name: str, quantity: int = 1):
    user_id = interaction.user.id
    items = user_inventory.get(user_id, [])
    
    if not items:
        await interaction.response.send_message("🎒 Trong túi có cái lol gì đâu mà bán =))))", ephemeral=True)
        return
    
    total_earn = 0
    sold_items = []
    
    if item_name.lower() == "all":
        # Bán tất cả đồ rác rưởi và thường (giữ đồ hiếm)
        to_sell = []
        to_keep = []
        
        for item in items:
            if item["rarity"] in ["💩 Rác rưởi", "⭐ Thường"]:
                to_sell.append(item)
            else:
                to_keep.append(item)
        
        if not to_sell:
            await interaction.response.send_message("💀 M toàn đồ hiếm thì bán làm gì? Giữ đi!", ephemeral=True)
            return
        
        for item in to_sell:
            total_earn += item["sell_price"]
            sold_items.append(f"{item['name']} ({item['sell_price']}xu)")
        
        user_inventory[user_id] = to_keep
        user_balance[user_id] += total_earn
        
        embed = discord.Embed(title="💰 Bán hàng loạt", color=0x00ff00)
        embed.add_field(name="Đã bán", value="\n".join(sold_items[:10]) + (f"\n... và {len(sold_items)-10} cái khác" if len(sold_items) > 10 else ""), inline=False)
        embed.add_field(name="💵 Thu được", value=f"**{total_earn} xu**", inline=True)
        embed.add_field(name="💎 Số dư mới", value=f"**{user_balance[user_id]} xu**", inline=True)
        await interaction.response.send_message(embed=embed)
        return
    
    # Bán item cụ thể
    found_items = [i for i in items if i["name"].lower() == item_name.lower()]
    
    if not found_items:
        await interaction.response.send_message(f"K có item tên `{item_name}` trong túi m, check lại `/gacha_inventory` đi 💀", ephemeral=True)
        return
    
    if quantity > len(found_items):
        await interaction.response.send_message(f"M chỉ có {len(found_items)} cái `{item_name}`, bán {quantity} cái kiểu gì =))))", ephemeral=True)
        return
    
    # Tính tiền và xóa item
    for i in range(quantity):
        item = found_items[i]
        total_earn += item["sell_price"]
        sold_items.append(f"{item['name']} ({item['sell_price']}xu)")
        user_inventory[user_id].remove(item)
    
    user_balance[user_id] += total_earn
    
    embed = discord.Embed(title="💰 Bán thành công", color=0x00ff00)
    embed.add_field(name="Đã bán", value="\n".join(sold_items), inline=False)
    embed.add_field(name="💵 Thu được", value=f"**{total_earn} xu**", inline=True)
    embed.add_field(name="💎 Số dư mới", value=f"**{user_balance[user_id]} xu**", inline=True)
    embed.set_footer(text="Dùng /gacha_inventory để xem đồ còn lại")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gacha_shop", description="Xem giá bán các loại rarity")
async def gacha_shop_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🏪 Giá bán item theo độ hiếm", color=0xffcc00)
    embed.add_field(name="🎲 Quay 1 lần", value=f"`{GACHA_COST} xu`", inline=False)
    
    for rarity, config in RARITY_CONFIG.items():
        embed.add_field(
            name=rarity,
            value=f"Tỉ lệ: {config['weight']}% | Giá bán: `{config['sell_price']} xu`",
            inline=False
        )
    
    embed.set_footer(text="Mỗi user bắt đầu với 100 xu | /gacha để quay")
    await interaction.response.send_message(embed=embed)
# ---------- Main ----------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(TOKEN)