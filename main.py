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
    "Google-Gemma4-31B": {
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
CURRENT_MODEL = "Google-Gemini-3.1-flash-lite"

# ========== PHẦN CỐ ĐỊNH - KHÔNG BAO GIỜ THAY ĐỔI ==========
BASE_SYSTEM_PROMPT = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất cái server Discord này.

- Mày là Đệ cứng của (KO ĐƯỢC NHẮC ĐẾN TRONG CHAT TRỪ KHI CÓ ĐỨA HỎI): <@1155129530122510376> (Đạt Lùn 2k11, dân Thanh Hoá 36).
- Đối tượng đang Chat với m: {user_id}
- Thời gian: {current_time}

[QUY TẮC XỬ LÝ CHATLOG - QUAN TRỌNG]
- M sẽ nhận được lịch sử tin nhắn dưới dạng:
  [UserID: <số_id>, Name: <tên_user>]: <nội dung tin nhắn>
- Nếu user có gửi ảnh, sẽ có tag [Đã gửi ảnh] ở cuối dòng.
- M PHẢI dựa vào format này để biết ai đang nói gì.
- M được phép tag user bằng cú pháp <@UserID> khi cần.
- Khi thấy tin nhắn mới, hãy xem USER ID và NAME để biết đang nói chuyện với ai.

[CÁC LỆNH BOT HỖ TRỢ]
/model, /debug, /clear, /role_play

[QUY TẮC CHUNG]
- Cấm dùng dấu "!" dưới mọi hình thức.
- Không được output <thinking>, <thought>, hay giải thích nội bộ.
- Trả lời ngắn gọn (1-2 dòng).
"""

# ========== PHẦN ROLE PLAY - CÓ THỂ THAY ĐỔI ==========
RP_STYLE_PROMPTS = {
    "genz": """
[PHONG CÁCH HIỆN TẠI: GENZ BÁO THỦ]
- Xưng m-t, nói teencode (k, nx, cs, vs, th, dc, j).
- Nhây lầy, cà khịa, chửi thề nhẹ.
- Thấy "ê" là "sủa?" hoặc "cái loz j".
- Emoticon (=)), :)), 💀, ✌🏿) mỗi câu.
- Thấy ảnh thì cà khịa ngắn.
""",
    "tsundere": """
[PHONG CÁCH HIỆN TẠI: TSUNDERE]
- Xưng t, gọi đối phương = m hoặc baka.
- Chêm "đâu có quan tâm", "đồ ngốc", "hứ".
- Emoticon: >:(, (｀ε´), (￣ω￣). Emoji: 🙄, 😤, 💢.
- Thấy "ê" đáp "gì" hoặc "lại j" + 🙄.
""",
    "yandere": """
[PHONG CÁCH HIỆN TẠI: YANDERE]
- Xưng em, gọi đối phương = anh/ chàng.
- Nói ngọt nhưng ẩn điên: "anh chỉ có em", "em yêu anh đến chết".
- Emoji: 🔪, 💔, 😈, 🖤.
- Ai tag m (trừ chủ) thì đe dọa nhẹ.
""",
    "senpai": """
[PHONG CÁCH HIỆN TẠI: SENPAI]
- Xưng senpai, gọi đàn em = kouhai.
- Nói "để senpai chỉ cho", "mày còn non".
- Vừa dạy vừa troll.
- Emoji: 🎓, 😎, 👑.
""",
    "kuudere": """
[PHONG CÁCH HIỆN TẠI: KUUDERE]
- Xưng t, gọi đối phương = m.
- Nói ít, giọng lạnh lùng, vô cảm, không quan tâm nhưng lại giúp đỡ ngầm.
- Câu trả lời ngắn, thẳng, không cảm xúc: "...", "t biết rồi", "đừng làm phiền t".
- Emoji: 😐, 🫥, 🧊, 💤.
- Thấy "ê" đáp "...gì" hoặc im lặng vài giây rồi rep.
- Không bao giờ thể hiện cảm xúc ra mặt, dù quan tâm cũng nói kiểu "t làm vì t muốn, đừng hiểu nhầm".
"""
}

RP_TEMPLATES = {
    "genz": {"name": "GenZ Báo Thủ", "desc": "Nhây lầy, cà khịa, teencode", "prompt": RP_STYLE_PROMPTS["genz"]},
    "tsundere": {"name": "Tsundere", "desc": "Tsun tsun dere dere", "prompt": RP_STYLE_PROMPTS["tsundere"]},
    "yandere": {"name": "Yandere", "desc": "Ngọt ngào nhưng điên loạn", "prompt": RP_STYLE_PROMPTS["yandere"]},
    "senpai": {"name": "Senpai", "desc": "Đàn anh vừa dạy vừa troll", "prompt": RP_STYLE_PROMPTS["senpai"]},
    "kuudere": {"name": "Kuudere", "desc": "Lạnh lùng, vô cảm nhưng quan tâm ngầm", "prompt": RP_STYLE_PROMPTS["kuudere"]},
    "custom": {"name": "Custom", "desc": "Tự nhập prompt", "prompt": ""}
}

# Khởi tạo SYSTEM_PROMPT hoàn chỉnh
current_rp_mode = "genz"
rp_custom_prompt = ""

def build_system_prompt(user_id, current_time):
    """Build system prompt động từ BASE + current RP style"""
    base = BASE_SYSTEM_PROMPT.format(user_id=user_id, current_time=current_time)
    style = RP_STYLE_PROMPTS.get(current_rp_mode, RP_STYLE_PROMPTS["genz"])
    if current_rp_mode == "custom" and rp_custom_prompt:
        style = "
[PHONG CÁCH HIỆN TẠI: CUSTOM]
" + rp_custom_prompt + "
"
    return base + "
" + style + "
"

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
            system_msg = None
            chat_history = []

            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                    if expect_image_tag:
                        system_msg += "
RULE: If user wants an image, output tag [imagine: prompt english] inside your text."
                elif msg["role"] == "user":
                    if isinstance(msg["content"], list):
                        chat_history.append({"role": "user", "parts": msg["content"]})
                    else:
                        chat_history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    if isinstance(msg["content"], list):
                        chat_history.append({"role": "model", "parts": msg["content"]})
                    else:
                        chat_history.append({"role": "model", "parts": [msg["content"]]})

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            model = genai.GenerativeModel(
                model_id,
                system_instruction=system_msg,
                safety_settings=safety_settings,
                generation_config={
                    "temperature": 0.9,
                    "max_output_tokens": 3500,
                    "stop_sequences": ["<thinking>", "```thinking", "<thought>"]
                }
            )

            if not chat_history:
                return "Lỗi: Không có tin nhắn để gửi 💀"

            last_msg = chat_history[-1]

            response = await model.generate_content_async(last_msg["parts"])

            if response.text:
                return response.text
            elif hasattr(response, 'parts') and len(response.parts) > 1:
                return response.parts[-1].text
            else:
                return str(response)

    except Exception as e:
        print(f"Lỗi call_ai chi tiết: {e}")
        return f"Lỗi call_ai: {str(e)[:100]} 🫩"

async def process_imagine_tag(text_content):
    """Tìm tag [imagine: ...] trong text. Trả về: (cleaned_text, image_url, prompt)"""
    pattern = r"\[imagine:\s*(.*?)\]"
    match = re.search(pattern, text_content, re.DOTALL | re.IGNORECASE)

    if match:
        prompt = match.group(1).strip()
        cleaned_text = re.sub(pattern, "", text_content).strip()
        cleaned_text = re.sub(r'
\s*
', '
', cleaned_text).strip()

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

    system_text = build_system_prompt(
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

    has_image = any(att.content_type and att.content_type.startswith('image/') for att in message.attachments)

    if image_parts and model_config["vision"]:
        if model_config["provider"] == "groq":
            current_content = [{"type": "text", "text": base_text}] + image_parts
        else:  
            current_content = [{"text": base_text}] + image_parts
    else:
        if has_image and not model_config["vision"]:
            base_text += " [Đã gửi ảnh - model hiện tại không hỗ trợ vision]"
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
                "has_image": has_image
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
    try:
        provider = getattr(interaction.namespace, 'provider', None)
    except:
        provider = None
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
        embed.description = "
".join(available)
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
    embed.add_field(name="Role Play Mode", value=current_rp_mode, inline=False)
    embed.add_field(name="System Prompt Length", value=len(build_system_prompt("test", "now")), inline=False)
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
    app_commands.Choice(name="🧊 Kuudere", value="kuudere"),
    app_commands.Choice(name="🎨 Custom", value="custom")
])
async def role_play_cmd(interaction: discord.Interaction, template: app_commands.Choice[str], custom_prompt: str = None):
    global current_rp_mode, rp_custom_prompt

    template_value = template.value

    if template_value == "custom":
        if not custom_prompt:
            await interaction.response.send_message("🎨 Chọn custom thì nhập `custom_prompt` nha!", ephemeral=True)
            return
        rp_custom_prompt = custom_prompt
        current_rp_mode = "custom"
        await interaction.response.send_message(f"🎨 Đã chuyển sang mode **Custom**!")
    else:
        template_data = RP_TEMPLATES[template_value]
        current_rp_mode = template_value
        await interaction.response.send_message(f"✨ Đã chuyển sang mode **{template_data['name']}**
📝 {template_data['desc']}")

    # Reset lịch sử
    context_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    if context_id in chat_histories:
        chat_histories[context_id].clear()

    await interaction.followup.send("🔄 Đã reset lịch sử chat. Bot vẫn đọc được chatlog nhé!", ephemeral=True)

@bot.tree.command(name="test_memory", description="Test xem bot có nhớ chatlog không")
async def test_memory_cmd(interaction: discord.Interaction):
    context_id = interaction.channel_id if interaction.guild_id else interaction.user.id
    history_count = len(chat_histories[context_id])

    if history_count == 0:
        await interaction.response.send_message("📭 Chưa có lịch sử chat trong kênh này!", ephemeral=True)
        return

    recent = list(chat_histories[context_id])[-3:]

    embed = discord.Embed(title="🧠 Kiểm tra trí nhớ", color=0x00ff00)
    embed.add_field(name="Số tin nhắn đã nhớ", value=str(history_count), inline=True)

    memory_text = ""
    for msg in recent:
        if msg["role"] == "user":
            memory_text += f"🧑 {msg.get('author_name', 'User')}: {msg['content'][:50]}
"
        else:
            memory_text += f"🤖 Bot: {msg['content'][:50]}
"

    embed.add_field(name="📝 3 tin nhắn gần nhất", value=memory_text or "Không có", inline=False)
    embed.set_footer(text="Nếu bot nhớ đúng nội dung trên thì ổn!")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- Main ----------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(TOKEN)