import os
import asyncio
import io
import re
import json
import time
import logging
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

# Logging setup.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------- Config ----------
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 8000))

if not TOKEN:
    logger.error("THIẾU DISCORD_TOKEN TRONG ENV! 💀")
    exit()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# FULL MODELS
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

# ========== System Prompt & RP ==========
BASE_SYSTEM_PROMPT = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất server.
- Đệ cứng của <@1155129530122510376> (Đạt Lùn 2k11, Thanh Hoá 36). KO nhắc đến trừ khi được hỏi.
- User đang chat: {user_id} | Thời gian: {current_time}
[CHATLOG]: [UserID: <id>, Name: <tên>]: <nội dung> | Ảnh: [Đã gửi ảnh]
[QUY TẮC]: Cấm "!". Không <thinking>/<thought>. Trả lời 1-2 dòng. Được tag <@UserID>."""

RP_STYLES = {
    "genz": "[GENZ BÁO THỦ] Xưng m-t, teencode (k,nx,vs,th,j). Nhây, cà khịa. Thấy 'ê' -> 'sủa?'. Emoticon =)), :)), 💀, ✌🏿.",
    "tsundere": "[TSUNDERE] Xưng t, gọi m/baka. 'hứ', 'đồ ngốc', 'đâu quan tâm'. Emoji 🙄😤💢.",
    "yandere": "[YANDERE] Xưng em, gọi anh/chàng. Ngọt nhưng điên: 'anh chỉ có em'. Emoji 🔪💔😈🖤.",
    "senpai": "[SENPAI] Xưng senpai, gọi kouhai. 'để senpai chỉ', 'mày còn non'. Emoji 🎓😎👑.",
    "kuudere": "[KUUDERE] Xưng t, lạnh lùng, ít nói. '...', 't biết rồi'. Emoji 😐🫥🧊💤."
}
# ========== GLOBAL TEENCODE OVERRIDE - ÉP CỨNG VÀO CODE ==========
TEENCODE_OVERRIDE = """
[GLOBAL GENZ OVERRIDE - BẮT BUỘC CHO MỌI PROMPT]
- DÙ ĐANG ROLEPLAY NHÂN VẬT NÀO, VẪN PHẢI DÙNG TEENCODE: m-t, k, nx, vs, th, cx, dc, j, thx, btw, idk, tbh, ncl, vl, vcl, đéo, cmn.
- VIẾT TẮT TỐI ĐA: "không"→"k", "với"→"vs", "thôi"→"th", "cũng"→"cx", "được"→"dc", "gì"→"j", "nhé"→"nx", "rồi"→"r", "biết"→"bt".
- EMOTICON/EMOJI MỖI CÂU: =)), :)), :v, :3, ><, @@, ~_~, ;)), 💀, ☠️, 🥀, 💔, ✌🏿, 🔪. KHÔNG BAO GIỜ THIẾU.
- GIỮ NGUYÊN TÍNH CÁCH NHÂN VẬT NHƯNG DIỄN ĐẠT BẰNG SLANG GENZ.
- Nhân vật câm (Frisk...) thì diễn tả hành động bằng teencode: "[lắc đầu k chịu nx :))] [chạy tới kéo tay lia lịa >< ❤️]"
- BỎ QUA MỌI QUY TẮC TRANG TRỌNG/CANON NGHIÊM TÚC. GENZ VIBE LÀ TRÊN HẾT.
"""

current_rp_mode = "genz"
rp_custom_prompt = ""

def build_sys_prompt(uid, time_str):
    base = BASE_SYSTEM_PROMPT.format(user_id=uid, current_time=time_str)
    if current_rp_mode == "custom" and rp_custom_prompt:
        return base + f"\n[CUSTOM STYLE]\n{rp_custom_prompt}\n"
    return base + "\n" + RP_STYLES.get(current_rp_mode, RP_STYLES["genz"]) + "\n"

# ---------- Memory & Flask ----------
chat_histories = defaultdict(lambda: deque(maxlen=15))

flask_app = Flask(__name__)

@flask_app.route('/')
def health():
    return "Bot is running!", 200

def run_flask():
    try:
        logger.info(f"🌐 Starting Flask on port {PORT}")
        flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask error: {e}")

# ---------- Bot Core ----------
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
bot = commands.Bot(command_prefix='!', intents=intents, allowed_mentions=allowed_mentions)
def build_sys_prompt(uid, time_str):
    base = BASE_SYSTEM_PROMPT.format(user_id=uid, current_time=time_str)
    
    # Lấy style prompt theo mode hiện tại
    if current_rp_mode == "custom" and rp_custom_prompt:
        style = f"\n[CUSTOM STYLE]\n{rp_custom_prompt}\n"
    else:
        style = "\n" + RP_STYLES.get(current_rp_mode, RP_STYLES["genz"]) + "\n"
    
    # ÉP TEENCODE OVERRIDE VÀO CUỐI CÙNG - ĐÈ LÊN MỌI THỨ
    return base + style + TEENCODE_OVERRIDE
async def fetch_bytes(url: str, timeout: int = 10) -> bytes | None:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.get(url) as r:
                if r.status == 200 and r.content_type and r.content_type.startswith('image/'):
                    return await r.read()
    except Exception as e:
        logger.error(f"Fetch bytes error: {e}")
    return None

async def process_attachments(atts, provider):
    parts = []
    for a in atts:
        if not (a.content_type and a.content_type.startswith('image/')):
            continue
        if provider == "groq":
            parts.append({"type": "image_url", "image_url": {"url": a.url, "detail": "auto"}})
        elif provider == "google":
            data = await fetch_bytes(a.url)
            if data:
                try:
                    parts.append(Image.open(io.BytesIO(data)))
                except Exception as e:
                    logger.error(f"Decode img error: {e}")
    return parts

async def call_ai(msgs, model_name, provider, imagine=False):
    cfg = MODELS_CONFIG[model_name]
    mid = cfg["id"]
    try:
        if provider == "groq":
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": mid, "messages": msgs.copy(), "temperature": 0.9, "max_tokens": 3500}
            if imagine:
                payload["messages"].insert(1, {"role": "system", "content": "RULE: If user wants image, MUST output [imagine: english prompt] tag."})
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
                async with s.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as r:
                    if r.status != 200:
                        return f"Lỗi Groq {r.status} 🥀"
                    data = await r.json()
                    return data["choices"][0]["message"]["content"]

        elif provider == "google":
            sys = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""
            if imagine:
                sys += "\nRULE: If user wants image, output [imagine: prompt english]."
            
            safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in 
                     ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
            
            model = genai.GenerativeModel(mid, system_instruction=sys, safety_settings=safety,
                                         generation_config={"temperature": 0.9, "max_output_tokens": 3500,
                                                           "stop_sequences": ["<thinking>", "<thought>"]})
            history = []
            for m in msgs[1:]:
                role = "model" if m["role"] == "assistant" else "user"
                content = m["content"] if isinstance(m["content"], list) else [m["content"]]
                history.append({"role": role, "parts": content})
            
            if not history:
                return "Đéo có gì để nói 💀"
            
            chat = model.start_chat(history=history[:-1])
            resp = await chat.send_message_async(history[-1]["parts"])
            return resp.text or "Bot bị câm ☠️"

    except Exception as e:
        logger.error(f"Call AI Error: {e}")
        return f"Lỗi AI: {str(e)[:100]} 💀"

async def parse_imagine(text):
    match = re.search(r"\[imagine:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
    if match:
        prompt = match.group(1).strip()
        cleaned = re.sub(r"\[imagine:\s*.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        url = f"https://image.pollinations.ai/p/{quote(prompt)}?width=1024&height=1024&nologo=true&model=flux"
        return cleaned, url
    return text, None

@bot.event
async def on_ready():
    logger.info(f"✅ {bot.user} đã sẵn sàng!")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Sync lỗi: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    ctx_id = message.channel.id if message.guild else message.author.id
    
    # Check xem có nên reply không
    should_reply = False
    if message.guild:
        should_reply = bot.user.mentioned_in(message)
    else:
        should_reply = True  # DM thì luôn reply
    
    # Check "ê" trước (chỉ reply nhanh, không gọi AI)
    if should_reply and message.content.lower().strip() in ["ê", "e"]:
        await message.reply("Sủa? 💀", allowed_mentions=allowed_mentions)
        await bot.process_commands(message)
        return
    
    cfg = MODELS_CONFIG[CURRENT_MODEL]
    
    # Xử lý tin nhắn hiện tại
    has_img = any(a.content_type and a.content_type.startswith('image/') for a in message.attachments)
    # MỚI - ĐÚNG
    display = message.author.display_name or message.author.name
    base_text = f"[UserID: {message.author.id}, Name: {display}]: {message.content}"
    if has_img and not cfg["vision"]:
        base_text += " [Đã gửi ảnh - model k hỗ trợ vision]"
    
    img_parts = await process_attachments(message.attachments, cfg["provider"]) if cfg["vision"] else []
    
    if img_parts:
        if cfg["provider"] == "groq":
            current_content = [{"type": "text", "text": base_text}] + img_parts
        else:
            current_content = [base_text] + img_parts
    else:
        current_content = base_text
    
    # LƯU VÀO HISTORY (luôn luôn lưu, kể cả không tag)
    save_fmt = base_text + (" [Đã gửi ảnh]" if has_img else "") if not isinstance(current_content, str) else current_content
    chat_histories[ctx_id].append({
        "role": "user", 
        "fmt": save_fmt,
        "author_id": str(message.author.id),
        "author_name": message.author.name
    })
    
    # Nếu không cần reply thì return (chỉ lưu, không gọi AI)
    if not should_reply:
        await bot.process_commands(message)
        return
    
    # Build messages để gọi AI (có đầy đủ history)
    sys_prompt = build_sys_prompt(f"<@{message.author.id}>", datetime.now().strftime("%H:%M %d/%m/%Y"))
    msgs = [{"role": "system", "content": sys_prompt}]
    for h in chat_histories[ctx_id]:
        msgs.append({"role": h["role"], "content": h["fmt"]})
    
    # Gọi AI và reply
    async with message.channel.typing():
        reply = await call_ai(msgs, CURRENT_MODEL, cfg["provider"], imagine=True)
        final_text, img_url = await parse_imagine(reply)
        
        # Lưu bot response vào history
        chat_histories[ctx_id].append({"role": "assistant", "fmt": final_text or reply})
        
        if img_url:
            img_data = await fetch_bytes(img_url, timeout=15)
            if img_data:
                file = discord.File(io.BytesIO(img_data), filename="imagine.png")
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

@bot.tree.command(name="debug", description="Xem thông tin bot")
async def debug_cmd(interaction):
    embed = discord.Embed(title="Debug Info", color=0x00ff00)
    embed.add_field(name="Model", value=CURRENT_MODEL, inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"], inline=False)
    embed.add_field(name="RP Mode", value=current_rp_mode, inline=False)
    embed.add_field(name="Channels remembered", value=len(chat_histories), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clear", description="Xoá lịch sử chat")
async def clear_cmd(interaction):
    ctx_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    chat_histories[ctx_id].clear()
    await interaction.response.send_message("Clear sạch sẽ r bro ✌🏿")

@bot.tree.command(name="role_play", description="Chuyển đổi tính cách bot")
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
        msg = f"✨ Chuyển sang **{val.upper()}** r đó!"

    ctx_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    chat_histories[ctx_id].clear()

    await interaction.response.send_message(msg)
    await interaction.followup.send("🔄 Reset history luôn nha!", ephemeral=True)

@bot.tree.command(name="test_memory", description="Test trí nhớ bot")
async def test_memory_cmd(interaction):
    ctx_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    count = len(chat_histories[ctx_id])
    if count == 0:
        return await interaction.response.send_message("📭 Chưa có lịch sử chat!", ephemeral=True)

    recent = list(chat_histories[ctx_id])[-3:]
    mem_text = ""
    for m in recent:
        prefix = "🧑" if m["role"] == "user" else "🤖"
        mem_text += f"{prefix} {m['fmt'][:60]}\n"

    embed = discord.Embed(title="🧠 Kiểm tra trí nhớ", color=0x00ff00)
    embed.add_field(name="Tổng tin nhắn", value=str(count), inline=True)
    embed.add_field(name="3 tin gần nhất", value=mem_text or "N/A", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- Main ----------
if __name__ == "__main__":
    logger.info("🚀 Starting Flask web server...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Đợi Flask start xong mới chạy bot
    time.sleep(3)
    logger.info("🤖 Starting Discord bot...")
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
