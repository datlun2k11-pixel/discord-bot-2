import os
import asyncio
import io
import re
import random
import json
import base64
import edge_tts
import time
import logging
from collections import defaultdict, deque
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import threading
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from PIL import Image
import ollama
from ollama import AsyncClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------- Config ----------
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
PORT = int(os.getenv("PORT", 8000))

# ========== OLLAMA CLOUD CLIENT ==========
ollama_client = None
if OLLAMA_API_KEY:
    ollama_client = AsyncClient(
        host="https://ollama.com",
        headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'}
    )
else:
    logger.warning("⚠️ Thiếu OLLAMA_API_KEY, mấy model Ollama sẽ đéo chạy được đâu nha con báo ☠️")

# ========== EDGE TTS CONFIG ==========
VIETNAMESE_VOICES = {
    "hoaimy": "vi-VN-HoaiMyNeural",   
    "namminh": "vi-VN-NamMinhNeural", 
    "thanhtuyen": "vi-VN-ThanhTuyenNeural" 
}
CURRENT_TTS_VOICE = VIETNAMESE_VOICES["hoaimy"]

if not TOKEN:
    logger.error("THIẾU DISCORD_TOKEN TRONG ENV! 💀")
    exit()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# FULL MODELS
MODELS_CONFIG = {
    "Ollama-Minimax-M3": {"id": "minimax-m3", "provider": "ollama", "vision": False},
    "Ollama-Nemotron-3-Super": {"id": "nemotron-3-super", "provider": "ollama", "vision": False},
    "Google-Gemma3-27B": {"id": "gemma-3-27b-it", "provider": "google", "vision": True},
    "Google-Gemma3-12B": {"id": "gemma-3-12b-it", "provider": "google", "vision": True},
    "Google-Gemma4-31B": {"id": "gemma-4-31b-it", "provider": "google", "vision": True},
    "Google-Gemini-3.1-flash-lite": {"id": "gemini-3.1-flash-lite", "provider": "google", "vision": True},
    "Google-Gemini-3.5-flash": {"id": "gemini-3.5-flash", "provider": "google", "vision": True}
}
CURRENT_MODEL = "Ollama-Minimax-M3"

# ========== GLOBAL SETTINGS ==========
BOT_SETTINGS = {
    "temperature": 0.9,
    "max_tokens": 3500,
    "enable_vision": True
}

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
    "dandere": "[DANDERE NHÚT NHÁT] Xưng t, m. Ngập ngừng, lắp bắp 'ờ... ừm...'. Emoji: 😳, 🫣, 👉👈, 🥺."
}

TEENCODE_OVERRIDE = """
[GLOBAL GENZ OVERRIDE]
- DÙ ĐANG ROLEPLAY NHÂN VẬT NÀO, VẪN PHẢI DÙNG TEENCODE: k, nx, vs, th, cx, dc, j, thx, btw, vl, vcl, đéo...
- TƯƠNG TÁC EMOJI: Chèn tag [interaction: :emoji:] vào cuối câu để thả reaction.
- M ko có chức năng tạo ảnh, đừng bốc phét.

[QUY TẮC BẮT BUỘC CHO TAG [voice: ...]]
1. Tag [voice: nội dung] dùng để tạo file âm thanh TTS.
2. CẤM TUYỆT ĐỐI teencode, slang, icon BÊN TRONG TAG VOICE.
3. Phải viết HOÀN CHỈNH bằng tiếng Việt có dấu.
4. Cấm lạm dụng tính năng tạo voice.
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

OWNER_ID = 1155129530122510376 

def is_owner(interaction: discord.Interaction):
    return interaction.user.id == OWNER_ID

class RPSView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=30.0)
        self.author_id = author_id
        self.user_choice = None
        self.bot_choice = random.choice(["rock", "paper", "scissors"]) 

    @discord.ui.button(label="Búa 🗿", style=discord.ButtonStyle.blurple)
    async def btn_rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "rock")

    @discord.ui.button(label="Giấy 📄", style=discord.ButtonStyle.green)
    async def btn_paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "paper")

    @discord.ui.button(label="Kéo ✂️", style=discord.ButtonStyle.red)
    async def btn_scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "scissors")

    async def _handle_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Nút của người ta mà m bấm j vậy? Vô duyên vl 💔", ephemeral=True)
        
        self.user_choice = choice
        self.stop()
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

async def generate_edge_tts(text: str, retries: int = 2) -> bytes | None:
    clean_text = re.sub(r'[^\w\s.,!?;:\-àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', ' ', text)
    
    if len(clean_text.strip()) < 3:
        return None

    for attempt in range(retries + 1):
        try:
            communicate = edge_tts.Communicate(clean_text, CURRENT_TTS_VOICE)
            audio_data = b""
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            if len(audio_data) > 100: 
                return audio_data
                
        except Exception as e:
            logger.error(f"❌ Attempt {attempt + 1} failed: {e}")
        
        if attempt < retries:
            await asyncio.sleep(1)

    return None

def parse_voice_tag(text: str) -> tuple[str, str | None]:
    pattern = r"\[voice:\s*(.*?)\]"
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        voice_text = match.group(1).strip()
        clean_text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
        return clean_text, voice_text
    
    return text, None

async def fetch_bytes(url: str, timeout: int = 15) -> bytes | None:
    import aiohttp
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.get(url, headers=headers) as r:
                if r.status == 200 and r.content_type and r.content_type.startswith('image/'):
                    return await r.read()
                return None
    except Exception as e:
        logger.error(f"Fetch bytes error: {e}")
        return None

async def process_attachments(atts, provider):
    parts = []
    for a in atts:
        if not (a.content_type and a.content_type.startswith('image/')):
            continue
        if provider == "ollama":
            data = await fetch_bytes(a.url)
            if data:
                # Ollama Cloud support base64 image format
                b64 = base64.b64encode(data).decode('utf-8')
                mime = a.content_type or "image/jpeg"
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
        elif provider == "google":
            data = await fetch_bytes(a.url)
            if data:
                try:
                    parts.append(Image.open(io.BytesIO(data)))
                except Exception as e:
                    logger.error(f"Decode img error: {e}")
    return parts

async def call_ai(msgs, model_name, provider):
    cleaned_msgs = []
    for m in msgs:
        content = m.get("content", "")
        if isinstance(content, str):
            if not content.strip(): 
                continue 
        elif isinstance(content, list):
            has_content = any(
                (c.strip() if isinstance(c, str) else (c.get("text", "").strip() if isinstance(c, dict) else True))
                for c in content
            )
            if not has_content:
                continue
            
        cleaned_msgs.append(m)
        
    if not cleaned_msgs:
        return "Đéo có gì để nói, m gửi prompt rỗng à? 💀"
        
    cfg = MODELS_CONFIG[model_name]
    mid = cfg["id"]
    
    temp = BOT_SETTINGS["temperature"]
    max_tok = BOT_SETTINGS["max_tokens"]
    
    try:
        if provider == "ollama":
            if not ollama_client:
                return "Thiếu OLLAMA_API_KEY, sao t gọi API dc hả bro? 💀"
            
            # Ollama Cloud format (support openai-style multimodal)
            response = await ollama_client.chat(
                model=mid, 
                messages=cleaned_msgs,
                options={"temperature": temp, "num_predict": max_tok},
                stream=False
            )
            return response['message']['content']

        elif provider == "google":
            sys = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""
            
            safety = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
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
    pattern = r"\[interaction:\s*(.+?)\]"
    matches = re.findall(pattern, text)
    
    if matches:
        for emoji_str in matches:
            emoji_str = emoji_str.strip()
            try:
                await message.add_reaction(emoji_str)
            except Exception as e:
                logger.error(f"Failed to add reaction {emoji_str}: {e}")
        
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
    
    reply_info = ""
    if message.reference and message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
        reply_info = f"(Reply @{message.reference.resolved.author.display_name}) "
    att_info = " [Đính kèm ảnh]" if any(a.content_type and a.content_type.startswith('image/') for a in message.attachments) else ""
    
    chat_histories[ctx_id].append(f"{display}: {reply_info}{message.content}{att_info}")
    
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
        
    cfg = MODELS_CONFIG[CURRENT_MODEL]
    use_vision = BOT_SETTINGS["enable_vision"] and cfg["vision"]
    
    past_msgs = list(chat_histories[ctx_id])[:-1]
    chatlog_str = "\n".join(past_msgs) if past_msgs else "Chưa có ai nói gì, im ắng như chùa bà đanh 🥀"
    
    sys_prompt = build_sys_prompt(f"<@{message.author.id}>", datetime.now().strftime("%H:%M %d/%m/%Y"), chatlog_str)
    
    clean_content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not clean_content and message.attachments:
        clean_content = "[User gửi ảnh]"
        
    base_text = f"{display}: {clean_content}"
    img_parts = await process_attachments(message.attachments, cfg["provider"]) if use_vision else []
    
    if img_parts:
        current_content = [{"type": "text", "text": base_text}] + img_parts
    else:
        current_content = base_text
        
    msgs = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": current_content}]
    
    async with message.channel.typing():
        try:
            reply = await call_ai(msgs, CURRENT_MODEL, cfg["provider"])
            
            final_text, voice_text = parse_voice_tag(reply)
            final_text = await parse_interactions(message, final_text)
            
            chat_histories[ctx_id].append(f"Bot: {final_text}")
            
            if voice_text:
                audio_data = await generate_edge_tts(voice_text)
                
                if audio_data:
                    audio_file = discord.File(
                        io.BytesIO(audio_data),
                        filename="voice.mp3",
                        description=f"Voice message: {voice_text}"
                    )
                    
                    await message.reply(
                        content=final_text if final_text else None,
                        file=audio_file,
                        allowed_mentions=allowed_mentions
                    )
                else:
                    await message.reply(final_text, allowed_mentions=allowed_mentions)
            else:
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
    app_commands.Choice(name="Ollama", value="ollama"),
    app_commands.Choice(name="Google", value="google")
])
@app_commands.autocomplete(model_id=model_autocomplete)
async def model_cmd(interaction, provider: str = None, model_id: str = None, custom_model_id: str = None):
    global CURRENT_MODEL

    if not provider:
        return await interaction.response.send_message("Chọn provider đi bro 🥀", ephemeral=True)

    provider = provider.lower()
    if provider not in ["ollama", "google"]:
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

@bot.tree.command(name="voice", description="Đổi giọng TTS (Owner Only)")
@app_commands.check(is_owner)
@app_commands.choices(voice=[
    app_commands.Choice(name="Hoài My (Nữ, nhẹ nhàng)", value="hoaimy"),
    app_commands.Choice(name="Nam Minh (Nam, trầm ấm)", value="namminh"),
    app_commands.Choice(name="Thanh Tuyền (Nữ, cao vút)", value="thanhtuyen")
])
async def voice_cmd(interaction, voice: app_commands.Choice[str]):
    global CURRENT_TTS_VOICE
    if voice.value in VIETNAMESE_VOICES:
        CURRENT_TTS_VOICE = VIETNAMESE_VOICES[voice.value]
        await interaction.response.send_message(f"🎤 Đổi giọng sang **{voice.name}** r đó bro ✌🏿", ephemeral=True)
    else:
        await interaction.response.send_message("Giọng k hợp lệ 💀", ephemeral=True)

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
    
    vis_status = "On" if BOT_SETTINGS["enable_vision"] else "Off"
    embed.add_field(name="Settings", value=f"Temp: {BOT_SETTINGS['temperature']}\nMaxTok: {BOT_SETTINGS['max_tokens']}\nVision: {vis_status}", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clear", description="Xoá lịch sử chat")
async def clear_cmd(interaction):
    ctx_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    chat_histories[ctx_id].clear()
    await interaction.response.send_message("Clear sạch sẽ r bro ✌🏿")

@bot.tree.command(name="summer_game", description="Oẳn tù tì với bot")
async def summer_game_cmd(interaction: discord.Interaction):
    view = RPSView(interaction.user.id)
    
    embed = discord.Embed(
        title="🌊 Summer Game: Oẳn Tù Tì", 
        description="Bot đã chốt đơn trong bóng tối rồi nha.\nBấm nút bên dưới để quyết đấu đi bro! ⏳", 
        color=0x7289da
    )
    await interaction.response.send_message(embed=embed, view=view)
    
    await view.wait()
    
    if not view.user_choice:
        return await interaction.edit_original_response(
            content="Hết giờ rồi mà k chịu bấm, mày sợ hả? Nhát gan vl ☠️", 
            embed=None, view=None
        )
    
    u = view.user_choice
    b = view.bot_choice
    emojis = {"rock": "🗿", "paper": "📄", "scissors": "✂️"}
    
    if u == b:
        result_text = "Hòa"
        score = "Mày: 0 | Bot: 0"
    elif (u == "rock" and b == "scissors") or \
         (u == "paper" and b == "rock") or \
         (u == "scissors" and b == "paper"):
        result_text = "Mày thắng"
        score = "Mày: +1 | Bot: 0"
    else:
        result_text = "Bot thắng"
        score = "Mày: 0 | Bot: +1"
        
    await interaction.edit_original_response(content="🤔 Đang nhờ AI soạn văn tế...", embed=None, view=None)
    
    prompt = f"""Kết quả oẳn tù tì: User ra {emojis[u]}, Bot ra {emojis[b]}. Kết quả: {result_text}.
Hãy viết 1 câu bình luận ngắn gọn (dưới 20 từ) bằng giọng GenZ nhây, cà khịa. Dùng teencode + emoji. KHÔNG markdown."""

    try:
        cfg = MODELS_CONFIG[CURRENT_MODEL]
        msgs = [{"role": "user", "content": prompt}]
        ai_comment = await call_ai(msgs, CURRENT_MODEL, cfg["provider"])
        
        if not ai_comment or not ai_comment.strip():
            if result_text == "Mày thắng":
                ai_comment = "Thắng rồi thì làm j? Cay vl 😤"
            elif result_text == "Bot thắng":
                ai_comment = "Gà vcl, về nhà luyện thêm đi bro =))"
            else:
                ai_comment = "Hòa hả? Xui xẻo vãi chưởng 🥀"
                
    except Exception as e:
        logger.error(f"RPS AI error: {e}")
        ai_comment = "Bot bị đứng hình, thôi tính mày thắng đi cho lẹ =))"
    
    color_map = {"Mày thắng": 0x00ff00, "Bot thắng": 0xff0000, "Hòa": 0xffff00}
    final_embed = discord.Embed(title=f"🎮 Kết Quả: {result_text}", description=ai_comment, color=color_map.get(result_text, 0x7289da))
    final_embed.add_field(name="Lượt đấu", value=f"{emojis[u]} vs {emojis[b]}", inline=False)
    final_embed.add_field(name="Tỉ số", value=score, inline=False)
    final_embed.set_footer(text="Bot chốt trước khi mày bấm, gian lận cái dái 🤡")
    
    await interaction.edit_original_response(content=None, embed=final_embed, view=None)

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