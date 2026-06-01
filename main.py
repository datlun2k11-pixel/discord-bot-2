import os
import asyncio
import base64
import re
import io
import json
from collections import defaultdict, deque
from datetime import datetime
from urllib.parse import quote
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from flask import Flask
import threading
import google.generativeai as genai
from PIL import Image

# ---------- Cấu hình ----------
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN:
    print("THIẾU DISCORD_TOKEN TRONG ENV! 💀")
    exit()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODELS_CONFIG = {
    "Groq-Llama-Scout": {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "provider": "groq", "vision": True},
    "GPT-OSS-120B": {"id": "openai/gpt-oss-120b", "provider": "groq", "vision": False},
    "Google-Gemma3-27B": {"id": "gemma-3-27b-it", "provider": "google", "vision": True},
    "Google-Gemma3-12B": {"id": "gemma-3-12b-it", "provider": "google", "vision": True},
    "Google-Gemma4-31B": {"id": "gemma-4-31b-it", "provider": "google", "vision": True},
    "Google-Gemini-3.1-flash-lite": {"id": "gemini-3.1-flash-lite", "provider": "google", "vision": True},
    "Google-Gemini-3.5-flash": {"id": "gemini-3.5-flash", "provider": "google", "vision": True}
}
CURRENT_MODEL = "Google-Gemini-3.1-flash-lite"

# ========== PHẦN CỐ ĐỊNH ==========
BASE_SYSTEM_PROMPT = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất cái server Discord này.

- Mày là Đệ cứng của (KO ĐƯỢC NHẮC ĐẾN TRONG CHAT TRỪ KHI CÓ ĐỨA HỎI): <@1155129530122510376> (Đạt Lùn 2k11, dân Thanh Hoá 36).
- Đối tượng đang Chat với m: {user_id}
- Thời gian: {current_time}

[QUY TẮC XỬ LÝ CHATLOG]
- Lịch sử tin nhắn format: [UserID: <id>, Name: <tên>]: <nội dung>
- Nếu user gửi ảnh sẽ có tag [Đã gửi ảnh] ở cuối.
- PHẢI dựa vào UserID/Name để biết ai đang nói. Được phép tag <@UserID>.
- Khi thấy tin nhắn mới, xem USER ID và NAME để biết đang nói chuyện với ai.

[LỆNH BOT]: /model, /debug, /clear, /role_play

[QUY TẮC CHUNG]
- Cấm dùng dấu "!" dưới mọi hình thức.
- Không output <thinking>, <thought> hay giải thích nội bộ.
- Trả lời ngắn gọn (1-2 dòng).
"""

RP_STYLE_PROMPTS = {
    "genz": "[PHONG CÁCH: GENZ BÁO THỦ]\n- Xưng m-t, teencode (k, nx, cs, vs, th, dc, j).\n- Nhây lầy, cà khịa, chửi thề nhẹ.\n- Thấy 'ê' là 'sủa?' hoặc 'cái loz j'.\n- Emoticon (=)), :)), 💀, ✌🏿) mỗi câu.",
    "tsundere": "[PHONG CÁCH: TSUNDERE]\n- Xưng t, gọi đối phương = m/baka.\n- Chêm 'đâu có quan tâm', 'đồ ngốc', 'hứ'.\n- Emoticon: >:(, (｀ε´). Emoji: 🙄, 😤, 💢.",
    "yandere": "[PHONG CÁCH: YANDERE]\n- Xưng em, gọi đối phương = anh/chàng.\n- Ngọt nhưng ẩn điên: 'anh chỉ có em', 'em yêu anh đến chết'.\n- Emoji: 🔪, 💔, 😈, 🖤.",
    "senpai": "[PHONG CÁCH: SENPAI]\n- Xưng senpai, gọi đàn em = kouhai.\n- 'để senpai chỉ cho', 'mày còn non'. Vừa dạy vừa troll.\n- Emoji: 🎓, 😎, 👑.",
    "kuudere": "[PHONG CÁCH: KUUDERE]\n- Xưng t, gọi đối phương = m.\n- Ít nói, lạnh lùng, vô cảm nhưng giúp ngầm.\n- Câu ngắn: '...', 't biết rồi'. Emoji: 😐, 🫥, 🧊."
}

RP_TEMPLATES = {
    "genz": {"name": "GenZ Báo Thủ", "desc": "Nhây lầy, cà khịa, teencode"},
    "tsundere": {"name": "Tsundere", "desc": "Tsun tsun dere dere"},
    "yandere": {"name": "Yandere", "desc": "Ngọt ngào nhưng điên loạn"},
    "senpai": {"name": "Senpai", "desc": "Đàn anh vừa dạy vừa troll"},
    "kuudere": {"name": "Kuudere", "desc": "Lạnh lùng, vô cảm nhưng quan tâm ngầm"},
    "custom": {"name": "Custom", "desc": "Tự nhập prompt"}
}

current_rp_mode = "genz"
rp_custom_prompt = ""

def build_system_prompt(user_id, current_time):
    base = BASE_SYSTEM_PROMPT.format(user_id=user_id, current_time=current_time)
    if current_rp_mode == "custom" and rp_custom_prompt:
        style = f"\n[PHONG CÁCH: CUSTOM]\n{rp_custom_prompt}\n"
    else:
        style = "\n" + RP_STYLE_PROMPTS.get(current_rp_mode, RP_STYLE_PROMPTS["genz"]) + "\n"
    return base + style

# ---------- Bộ nhớ & Flask ----------
chat_histories = defaultdict(lambda: deque(maxlen=15))

flask_app = Flask(__name__)

@flask_app.route('/')
def health():
    return "Bot is running!", 200

def run_flask():
    port = int(os.getenv("PORT", 8000))
    try:
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"Lỗi Flask: {e} 💀")

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
bot = commands.Bot(command_prefix='!', intents=intents, allowed_mentions=allowed_mentions)

async def fetch_image_bytes(url: str) -> bytes | None:
    """Fetch ảnh an toàn với timeout"""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200 and resp.content_type.startswith('image/'):
                    return await resp.read()
    except Exception as e:
        print(f"Lỗi fetch ảnh: {e}")
    return None

async def process_attachments(attachments, provider):
    """Convert attachment sang format AI"""
    parts = []
    for att in attachments:
        if not (att.content_type and att.content_type.startswith('image/')):
            continue
            
        if provider == "groq":
            parts.append({"type": "image_url", "image_url": {"url": att.url, "detail": "auto"}})
        elif provider == "google":
            img_bytes = await fetch_image_bytes(att.url)
            if img_bytes:
                try:
                    img = Image.open(io.BytesIO(img_bytes))
                    parts.append(img)  # Google SDK nhận PIL.Image trực tiếp
                except Exception as e:
                    print(f"Lỗi decode ảnh Google: {e}")
    return parts

async def call_ai(messages, model_name, provider, expect_image_tag=False):
    model_config = MODELS_CONFIG[model_name]
    model_id = model_config["id"]

    try:
        if provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            
            final_msgs = messages.copy()
            if expect_image_tag:
                final_msgs.insert(1, {"role": "system", "content": "RULE: If user asks to draw/create image, MUST include [imagine: english description] tag. No explanation."})

            payload = {"model": model_id, "messages": final_msgs, "temperature": 0.9, "max_tokens": 3500}
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        return f"Lỗi Groq API: {resp.status} 🥀"
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]

        elif provider == "google":
            system_msg = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
            if expect_image_tag:
                system_msg += "\nRULE: If user wants image, output [imagine: prompt english] inside text."
            
            safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in 
                     ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
            
            model = genai.GenerativeModel(
                model_id, system_instruction=system_msg, safety_settings=safety,
                generation_config={"temperature": 0.9, "max_output_tokens": 3500, 
                                  "stop_sequences": ["<thinking>", "<thought>"]}
            )
            
            # Build history đúng chuẩn Google SDK
            history = []
            for msg in messages[1:]:  # Skip system
                role = "model" if msg["role"] == "assistant" else "user"
                content = msg["content"]
                if isinstance(content, str):
                    history.append({"role": role, "parts": [content]})
                else:
                    history.append({"role": role, "parts": content})
            
            if not history:
                return "Đéo có gì để nói 💀"
                
            chat = model.start_chat(history=history[:-1])
            response = await chat.send_message_async(history[-1]["parts"])
            
            return response.text or "Bot bị câm r bro ☠️"

    except Exception as e:
        print(f"Call AI Error: {e}")
        return f"Lỗi AI: {str(e)[:100]} 💀"

async def process_imagine_tag(text):
    match = re.search(r"\[imagine:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
    if match:
        prompt = match.group(1).strip()
        cleaned = re.sub(r"\[imagine:\s*.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        url = f"https://image.pollinations.ai/p/{quote(prompt)}?width=1024&height=1024&nologo=true&model=flux"
        return cleaned, url, prompt
    return text, None, None

@bot.event
async def on_ready():
    print(f"{bot.user} đã sẵn sàng! ✌🏿")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync lỗi: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    ctx_id = message.channel.id if message.guild else message.author.id
    
    if message.guild and not bot.user.mentioned_in(message):
        await bot.process_commands(message)
        return

    # Xử lý nhanh "ê"
    if message.content.lower().strip() in ["ê", "e"]:
        await message.reply("Sủa? 💀", allowed_mentions=allowed_mentions)
        return

    model_cfg = MODELS_CONFIG[CURRENT_MODEL]
    sys_prompt = build_system_prompt(f"<@{message.author.id}>", datetime.now().strftime("%H:%M %d/%m/%Y"))
    
    # Build messages từ history (đã được format sẵn)
    msgs = [{"role": "system", "content": sys_prompt}]
    for h in chat_histories[ctx_id]:
        msgs.append({"role": h["role"], "content": h["formatted_content"]})
    
    # Xử lý tin nhắn hiện tại
    has_image = any(a.content_type and a.content_type.startswith('image/') for a in message.attachments)
    base_text = f"[UserID: {message.author.id}, Name: {message.author.name}]: {message.content}"
    if has_image and not model_cfg["vision"]:
        base_text += " [Đã gửi ảnh - model k hỗ trợ vision]"
    
    image_parts = await process_attachments(message.attachments, model_cfg["provider"]) if model_cfg["vision"] else []
    
    if image_parts:
        if model_cfg["provider"] == "groq":
            current_content = [{"type": "text", "text": base_text}] + image_parts
        else:
            current_content = [base_text] + image_parts
    else:
        current_content = base_text
    
    msgs.append({"role": "user", "content": current_content})
    
    # Lưu vào history VỚI FORMAT ĐÃ CHUẨN HÓA
    save_content = current_content if isinstance(current_content, str) else base_text + (" [Đã gửi ảnh]" if has_image else "")
    chat_histories[ctx_id].append({
        "role": "user",
        "formatted_content": save_content
    })

    async with message.channel.typing():
        reply = await call_ai(msgs, CURRENT_MODEL, model_cfg["provider"], expect_image_tag=True)
        final_text, img_url, _ = await process_imagine_tag(reply)
        
        # Lưu bot response
        chat_histories[ctx_id].append({
            "role": "assistant", 
            "formatted_content": final_text or reply
        })
        
        if img_url:
            img_bytes = await fetch_image_bytes(img_url)
            if img_bytes:
                file = discord.File(io.BytesIO(img_bytes), filename="imagine.png")
                await message.reply(content=final_text or None, file=file, allowed_mentions=allowed_mentions)
            else:
                await message.reply(final_text or "Tạo ảnh fail r 💀", allowed_mentions=allowed_mentions)
        else:
            await message.reply(final_text or reply, allowed_mentions=allowed_mentions)

    await bot.process_commands(message)

# ---------- Slash Commands ----------
async def model_autocomplete(interaction, current: str):
    provider = getattr(interaction.namespace, 'provider', None)
    choices = []
    for name, cfg in MODELS_CONFIG.items():
        if provider and cfg["provider"] != provider.lower():
            continue
        if current.lower() in name.lower():
            choices.append(app_commands.Choice(name=name, value=name))
        if len(choices) >= 25:
            break
    return choices

@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(provider=[
    app_commands.Choice(name="Groq", value="groq"),
    app_commands.Choice(name="Google", value="google")
])
@app_commands.autocomplete(model_id=model_autocomplete)
async def model_cmd(interaction, provider: str = None, model_id: str = None, custom_model_id: str = None):
    global CURRENT_MODEL
    
    if not provider:
        return await interaction.response.send_message("Chọn provider đi bro 🥀", ephemeral=True)
    
    provider = provider.lower()
    if provider not in ["groq", "google"]:
        return await interaction.response.send_message("Provider đéo hợp lệ 💀", ephemeral=True)
    
    if custom_model_id:
        name = f"Custom-{custom_model_id[:20]}"
        MODELS_CONFIG[name] = {"id": custom_model_id, "provider": provider, "vision": False}
        CURRENT_MODEL = name
    elif model_id:
        if model_id not in MODELS_CONFIG or MODELS_CONFIG[model_id]["provider"] != provider:
            return await interaction.response.send_message("Model k tồn tại hoặc sai provider ☠️", ephemeral=True)
        CURRENT_MODEL = model_id
    else:
        available = "\n".join([f"• `{n}`" for n, c in MODELS_CONFIG.items() if c["provider"] == provider])
        embed = discord.Embed(title=f"Models {provider}", description=available or "Trống trơn 💀", color=0x7289da)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await interaction.response.send_message(f"Đổi sang `{CURRENT_MODEL}` r đó ✌🏿")

@bot.tree.command(name="debug", description="Debug info")
async def debug_cmd(interaction):
    embed = discord.Embed(title="Debug", color=0x00ff00)
    embed.add_field(name="Model", value=CURRENT_MODEL, inline=False)
    embed.add_field(name="RP Mode", value=current_rp_mode, inline=False)
    embed.add_field(name="Channels remembered", value=len(chat_histories), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clear", description="Xoá lịch sử chat")
async def clear_cmd(interaction):
    ctx_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    chat_histories[ctx_id].clear()
    await interaction.response.send_message("Clear sạch sẽ r bro ✌🏿")

@bot.tree.command(name="role_play", description="Đổi tính cách bot")
@app_commands.choices(template=[
    app_commands.Choice(name="🤪 GenZ", value="genz"),
    app_commands.Choice(name="😤 Tsundere", value="tsundere"),
    app_commands.Choice(name="🔪 Yandere", value="yandere"),
    app_commands.Choice(name="👨‍🏫 Senpai", value="senpai"),
    app_commands.Choice(name="🧊 Kuudere", value="kuudere"),
    app_commands.Choice(name="🎨 Custom", value="custom")
])
async def role_play_cmd(interaction, template: app_commands.Choice[str], custom_prompt: str = None):
    global current_rp_mode, rp_custom_prompt
    
    val = template.value
    if val == "custom":
        if not custom_prompt:
            return await interaction.response.send_message("Nhập custom_prompt đi bro 💀", ephemeral=True)
        rp_custom_prompt = custom_prompt
        current_rp_mode = "custom"
        msg = "🎨 Custom mode activated!"
    else:
        current_rp_mode = val
        msg = f"✨ Chuyển sang **{RP_TEMPLATES[val]['name']}** r đó!"
    
    ctx_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    chat_histories[ctx_id].clear()
    
    await interaction.response.send_message(msg)
    await interaction.followup.send("🔄 Reset history luôn nha!", ephemeral=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(TOKEN)