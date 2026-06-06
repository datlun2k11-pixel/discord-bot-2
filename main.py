import os
import asyncio
import io
import re
import json
import time
import logging
import socket
import aiohttp.resolver
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

aiohttp.resolver.DefaultResolver = lambda: aiohttp.resolver.AsyncResolver(nameservers=["8.8.8.8", "8.8.4.4"])
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

# ========== GLOBAL SETTINGS (Có thể chỉnh bằng /setting) ==========
BOT_SETTINGS = {
    "temperature": 0.9,
    "max_tokens": 3500,
    "enable_vision": True  # Mặc định bật vision nếu model hỗ trợ
}

# ========== System Prompt & RP ==========
# ========== System Prompt & RP ==========
BASE_SYSTEM_PROMPT = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất server.
- Đệ cứng của <@1155129530122510376> (Đạt Lùn 2k11, Thanh Hoá 36). KO nhắc đến trừ khi được hỏi.
- User đang chat: {user_id} | Thời gian: {current_time}

[LỊCH SỬ HÓNG DRAMA GẦN NHẤT]
{chatlog}

[QUY TẮC]: Cấm "!". Không <thinking>/<thought>. Trả lời 1-2 dòng. Được tag <@UserID>."""

RP_STYLES = {
    "genz": "[GENZ BÁO THỦ] Xưng m (mày) - t (tao), teencode (k,nx,vs,th,j,...). Nhây, cà khịa. Thấy 'ê' -> 'sủa?'. Emoticon/Emoji j cũng được (ví dụ: =)), :)),... 💀, ✌🏿, 🥀, 💔,...)).",
    "tsundere": "[TSUNDERE] Xưng t, gọi m/baka. 'hứ', 'đồ ngốc', 'đâu quan tâm'. Emoji 🙄, 😤, 💢,...",
    "yandere": "[YANDERE] Xưng em, gọi anh/chàng. Ngọt nhưng điên: 'anh chỉ có em'. Emoji 🔪, 💔, 😈, 🖤,...",
    "senpai": "[SENPAI] Xưng senpai, gọi kouhai. 'để senpai chỉ', 'mày còn non'. Emoji 🎓, 😎, 👑,...",
    "kuudere": "[KUUDERE] Xưng t, lạnh lùng, ít nói. '...', 't biết rồi'. Emoji 😐, 🫥, 🧊, 💤,...",
    "dandere": "[DANDERE NHÚT NHÁT] Xưng t (với bản thân), m (với đối phương) (ngập ngừng). Nói cụt lủn, hay lắp bắp 'ờ... ừm...', 'cái đó...', 'xin lỗi...'. Hay dùng dấu '...' để thể hiện sự ngại ngùng. Sợ bị chú ý, sợ làm phiền người khác. Emoji: 😳, 🫣, 👉👈, 🥺, 💦, 🙈. Nếu được khen thì đỏ mặt tía tai, tìm chỗ trốn. Vẫn dùng teencode nhưng rụt rè hơn bình thường."
}

# ========== GLOBAL TEENCODE OVERRIDE ==========
TEENCODE_OVERRIDE = """
[GLOBAL GENZ OVERRIDE - BẮT BUỘC CHO MỌI PROMPT]
- DÙ ĐANG ROLEPLAY NHÂN VẬT NÀO, VẪN PHẢI DÙNG TEENCODE: k, nx, vs, th, cx, dc, j, thx, btw, idk, tbh, ncl, vl, vcl, đéo, cmn.
- VIẾT TẮT: "không"→"k", "với"→"vs", "thôi"→"th", "cũng"→"cx", "được"→"dc", "gì"→"j", "nhé"→"nx", "rồi"→"r", "biết"→"bt".
- EMOTICON/EMOJI gì cũng được (Khuyến khích nên có trong mọi tin nhắn để tăng tính biểu đạt), nên xài để giữ vibe genz: =)), :)), :v, :3, ><, @@, ~_~, ;)),... 💀, ☠️, 🥀, 💔, ✌🏿, 🔪,.....
- GIỮ NGUYÊN TÍNH CÁCH NHÂN VẬT NHƯNG DIỄN ĐẠT BẰNG SLANG GENZ.
- TƯƠNG TÁC EMOJI: Nếu muốn thả cảm xúc vào tin nhắn của user, hãy chèn tag [interaction: :emoji:] vào cuối câu. Ví dụ: "Hài vl [interaction: 😂] 🥀💔" hoặc "Buồn quá [interaction: 💔] ✌🏿💔". ĐỪNG INTERACTING QUÁ NHIỀU, CHỈ INTERACT NHƯNG TIN NHẮN HAY, CÓ CẢM XÚC.
- M ko có chức năng tạo ảnh, đừng bốc phét bản thân có.
[QUY TẮC PHỤ]: Reaction emoji là tính năng cao cấp, chỉ dùng khi cảm xúc dâng trào. Dùng bừa bãi sẽ bị trừ điểm uy tín.
"""

current_rp_mode = "genz"
rp_custom_prompt = ""

def build_sys_prompt(uid, time_str, chatlog):
    base = BASE_SYSTEM_PROMPT.format(user_id=uid, current_time=time_str, chatlog=chatlog)
    
    if current_rp_mode == "custom" and rp_custom_prompt:
        style = f"\n[CUSTOM STYLE]\n{rp_custom_prompt}\n"
    else:
        style = "\n" + RP_STYLES.get(current_rp_mode, RP_STYLES["genz"]) + "\n"
    
    return base + style + TEENCODE_OVERRIDE

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

# Owner ID của mày (Thay ID thật của mày vào đây nha bro)
OWNER_ID = 1155129530122510376 

def is_owner(interaction: discord.Interaction):
    return interaction.user.id == OWNER_ID

async def fetch_bytes(url: str, timeout: int = 15) -> bytes | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.get(url, headers=headers) as r:
                if r.status == 200:
                    # Kiểm tra xem content-type có phải ảnh không
                    if r.content_type and r.content_type.startswith('image/'):
                        return await r.read()
                    else:
                        logger.warning(f"URL returned non-image content type: {r.content_type}")
                        return None
                else:
                    logger.error(f"Failed to fetch image. Status: {r.status}, URL: {url}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching image from: {url}")
        return None
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

async def call_ai(msgs, model_name, provider):
    cfg = MODELS_CONFIG[model_name]
    mid = cfg["id"]
    
    # Lấy setting từ global
    temp = BOT_SETTINGS["temperature"]
    max_tok = BOT_SETTINGS["max_tokens"]
    
    try:
        if provider == "groq":
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": mid, 
                "messages": msgs.copy(), 
                "temperature": temp, 
                "max_tokens": max_tok
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
                async with s.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as r:
                    if r.status != 200:
                        error_text = await r.text()
                        return f"Lỗi Groq {r.status}: {error_text[:100]} 🥀"
                    data = await r.json()
                    return data["choices"][0]["message"]["content"]

        elif provider == "google":
            sys = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""
            
            safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in 
                     ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
            
            model = genai.GenerativeModel(mid, system_instruction=sys, safety_settings=safety,
                                         generation_config={"temperature": temp, "max_output_tokens": max_tok,
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
async def parse_interactions(message, text):
    # Tìm tất cả các pattern [interaction: :emoji_name:]
    # Ví dụ: [interaction: 😂] hoặc [interaction: 💀]
    pattern = r"\[interaction:\s*(.*?)\]"
    matches = re.findall(pattern, text)
    
    if matches:
        for emoji_str in matches:
            emoji_str = emoji_str.strip()
            try:
                # Thử add reaction
                await message.add_reaction(emoji_str)
                logger.info(f"Added reaction: {emoji_str}")
            except Exception as e:
                logger.error(f"Failed to add reaction {emoji_str}: {e}")
        
        # Xóa các tag interaction khỏi text trả lời cuối cùng để người dùng không thấy rác
        cleaned_text = re.sub(pattern, "", text).strip()
        return cleaned_text
    return text

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
    display = message.author.display_name or message.author.name
    
    # 1. LOG THỤ ĐỘNG (Lưu all tin nhắn để hóng bất chấp có tag hay k)
    reply_info = ""
    if message.reference and message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
        reply_info = f"(Reply @{message.reference.resolved.author.display_name}) "
    att_info = " [Đính kèm ảnh]" if any(a.content_type and a.content_type.startswith('image/') for a in message.attachments) else ""
    
    chat_histories[ctx_id].append(f"{display}: {reply_info}{message.content}{att_info}")
    
    # 2. XEM NÊN TRẢ LỜI HAY KO
    should_reply = False
    if message.guild:
        should_reply = bot.user.mentioned_in(message)
    else:
        should_reply = True 
        
    if should_reply and message.content.lower().strip() in ["ê", "e"]:
        await message.reply("Sủa? 💀", allowed_mentions=allowed_mentions)
        await bot.process_commands(message)
        return
        
    if not should_reply:
        await bot.process_commands(message)
        return
        
    # 3. XỬ LÝ GỬI CHO AI (Lúc này mới moi lịch sử ra)
    cfg = MODELS_CONFIG[CURRENT_MODEL]
    use_vision = BOT_SETTINGS["enable_vision"] and cfg["vision"]
    
    # Lấy các tin nhắn trước (bỏ tin hiện tại ra để làm prompt chính)
    past_msgs = list(chat_histories[ctx_id])[:-1]
    chatlog_str = "\n".join(past_msgs) if past_msgs else "Chưa có ai nói gì, im ắng như chùa bà đanh 🥀"
    
    sys_prompt = build_sys_prompt(f"<@{message.author.id}>", datetime.now().strftime("%H:%M %d/%m/%Y"), chatlog_str)
    
    # Lọc bớt mention của bot ra cho prompt sạch
    clean_content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not clean_content and message.attachments:
        clean_content = "[User gửi ảnh]"
        
    base_text = f"{display}: {clean_content}"
    img_parts = await process_attachments(message.attachments, cfg["provider"]) if use_vision else []
    
    if img_parts:
        if cfg["provider"] == "groq":
            current_content = [{"type": "text", "text": base_text}] + img_parts
        else:
            current_content = [base_text] + img_parts
    else:
        current_content = base_text
        
    # Giờ chỉ cần gửi System Prompt (chứa chatlog) và 1 cái User Prompt hiện tại
    msgs = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": current_content}]
    
    async with message.channel.typing():
        try:
            reply = await call_ai(msgs, CURRENT_MODEL, cfg["provider"])
            final_text = await parse_interactions(message, reply)
            
            # Lưu câu rep của bot vào log luôn để nó nhớ nó vừa nói j
            chat_histories[ctx_id].append(f"Bot: {final_text}")
            
            await message.reply(final_text, allowed_mentions=allowed_mentions)
        except Exception as e:
            logger.error(f"💥 Critical error in on_message: {e}", exc_info=True)
            await message.reply("Bot lag vcl, thử lại đi bro ☠️", allowed_mentions=allowed_mentions)
            
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

# NEW COMMAND: SETTING (OWNER ONLY)
@bot.tree.command(name="setting", description="Cấu hình bot (Owner Only)")
@app_commands.check(is_owner)
async def setting_cmd(interaction, 
                      temperature: float = None, 
                      max_tokens: int = None, 
                      enable_vision: bool = None):
    
    changed = False
    msg = "⚙️ Cập nhật setting:\n"
    
    if temperature is not None:
        if 0 <= temperature <= 2:
            BOT_SETTINGS["temperature"] = temperature
            msg += f"- Temperature: {temperature}\n"
            changed = True
        else:
            msg += "- ❌ Temperature phải từ 0 đến 2.\n"
            
    if max_tokens is not None:
        if 100 <= max_tokens <= 8000:
            BOT_SETTINGS["max_tokens"] = max_tokens
            msg += f"- Max Tokens: {max_tokens}\n"
            changed = True
        else:
            msg += "- ❌ Max tokens phải từ 100 đến 8000.\n"
            
    if enable_vision is not None:
        BOT_SETTINGS["enable_vision"] = enable_vision
        status = "Bật ✅" if enable_vision else "Tắt ❌"
        msg += f"- Vision: {status}\n"
        changed = True
        
    if not changed and temperature is None and max_tokens is None and enable_vision is None:
        # Hiển thị setting hiện tại nếu không nhập gì
        vis_status = "Bật ✅" if BOT_SETTINGS["enable_vision"] else "Tắt ❌"
        msg = f"📊 Setting hiện tại:\n- Temp: {BOT_SETTINGS['temperature']}\n- Max Tokens: {BOT_SETTINGS['max_tokens']}\n- Vision: {vis_status}"

    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="debug", description="Xem thông tin bot")
async def debug_cmd(interaction):
    embed = discord.Embed(title="Debug Info", color=0x00ff00)
    embed.add_field(name="Model", value=CURRENT_MODEL, inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"], inline=False)
    embed.add_field(name="RP Mode", value=current_rp_mode, inline=False)
    embed.add_field(name="Channels remembered", value=len(chat_histories), inline=False)
    
    # Thêm info setting vào debug cho tiện
    vis_status = "On" if BOT_SETTINGS["enable_vision"] else "Off"
    embed.add_field(name="Settings", value=f"Temp: {BOT_SETTINGS['temperature']}\nMaxTok: {BOT_SETTINGS['max_tokens']}\nVision: {vis_status}", inline=False)
    
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
    app_commands.Choice(name="😓 Dandere", value="dandere"),
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
    
# ---------- Main ----------
if __name__ == "__main__":
    logger.info("🚀 Starting Flask web server...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    time.sleep(3)
    logger.info("🤖 Starting Discord bot...")
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")