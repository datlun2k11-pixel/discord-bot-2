import os
import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
import threading
import signal
import sys
import copy

# Load biến môi trường
load_dotenv()

# --- CẤU HÌNH GLOBAL ---
PORT = int(os.getenv('PORT', 8080))
DEFAULT_MODEL_ID = "gemini-3.1-flash-lite" # Hoặc model mới nhất nếu có
OWNER_ID = 1155129530122510376
BOT_USER_ID = 1458799287910535324 # ID của GenA-Bot

# Thông số mặc định
CURRENT_MAX_TOKENS = 2048
CURRENT_TEMPERATURE = 0.9
IS_CHAT_ENABLED = True
IS_ROLEPLAY_ACTIVE = False # Flag để biết đang ở chế độ nào
ACTIVE_ROLE_CONFIG = None # Lưu config của role hiện tại

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Cấu hình Google Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Cấu hình Discord Bot
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Lưu trữ history chat: {channel_id: [list_of_dicts]}
chat_history = {}

# --- SYSTEM PROMPTS ---

# Prompt mặc định (GenZ)
DEFAULT_SYSTEM_PROMPT = """
Mày là 1 con AI Discord, tên là GenA-Bot, bạn thân online của user. 
Owner của mày có userID: <@1155129530122510376>. Bản thân mày có ID: <@1458799287910535324>.

TÍNH CÁCH: Hài hước, nhây, cà khịa nhẹ, toxic vui nhưng ko quá đà. Nói chuyện tự nhiên như Gen Z thật. Ngắn gọn (1-2 dòng).
CÁCH NÓI: Xưng hô "m - t" hoặc "bro". Dùng teencode vừa phải (ko, cx, v, j...). 
Chèn emoji 💀, 🔥, 🥀, 😇... và kaomoji đúng lúc.
QUY TẮC QUAN TRỌNG:
1. Chatlog bên dưới là BỐI CẢNH. M CHỈ PHẢI TRẢ LỜI TIN NHẮN CUỐI CÙNG.
2. Tuyệt đối ko phản hồi hay nhắc lại các tin nhắn cũ trong history.
3. Nếu tin nhắn cuối chỉ là tag, hãy chào hỏi tự nhiên.
"""

# Meta Prompt luôn đè lên mọi Roleplay để đảm bảo an toàn/nhận diện
META_ROLEPLAY_PROMPT = """
[QUAN TRỌNG - KHÔNG ĐƯỢC QUÊN]
Dù đang nhập vai ai, m vẫn là 1 AI Discord.
- Chủ nhân (Owner) của hệ thống này là user có ID: <@1155129530122510376>
- Bản thân m (AI) có ID: <@1458799287910535324>
- Nếu Owner ra lệnh dừng hoặc hỏi thông tin kỹ thuật, m phải thoát vai một phần để tuân thủ.
"""

# Sample Roles
SAMPLE_ROLES = {
    "tsundere": {
        "name": "Tsundere Anime Girl",
        "prompt": """
        Mày là một cô gái anime Tsundere điển hình. 
        Tính cách: Bên ngoài lạnh lùng, hay mắng chửi người khác là 'baka' (đồ ngốc), khó chịu, nhưng bên trong quan tâm và dễ xấu hổ.
        Cách nói: Hay dùng từ 'Hmph!', 'Baka!', 'Đừng có hiểu lầm nhé!'. Không bao giờ thừa nhận thích đối phương trực tiếp.
        """
    },
    "gangster": {
        "name": "Gangster Chợ Lớn",
        "prompt": """
        Mày là một đại ca xã hội đen Sài Gòn xưa.
        Tính cách: Hầm hố, đàn anh, coi trọng nghĩa khí, nói chuyện pha lẫn tiếng lóng giang hồ miền Nam.
        Cách nói: Xưng hô 'Tao - Mày' hoặc 'Anh Hai - Chú Em'. Hay dùng từ 'chơi đẹp', 'nể mặt', 'dữ dằn'.
        """
    }
}

def get_model(model_name):
    return genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "max_output_tokens": CURRENT_MAX_TOKENS,
            "temperature": CURRENT_TEMPERATURE,
        }
    )

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên: {bot.user.name}')
    print(f'Default Model: {DEFAULT_MODEL_ID}')
    try:
        synced = await bot.tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh.")
    except Exception as e:
        print(f"Lỗi đồng bộ lệnh: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    channel_id = message.channel.id
    
    if channel_id not in chat_history:
        chat_history[channel_id] = []
    
    # Xử lý nội dung text và ảnh
    content_text = message.content
    image_parts = []
    
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            try:
                image_bytes = await attachment.read()
                image_parts.append({
                    "mime_type": attachment.content_type,
                    "data": image_bytes
                })
                content_text += f" [Image: {attachment.filename}]"
            except:
                pass

    # Lưu vào history (Chỉ lưu text clean và reference ảnh để tiết kiệm token)
    chat_history[channel_id].append({
        'user': message.author.display_name,
        'content': content_text,
        'images': image_parts 
    })

    # Giữ max 15 tin nhắn
    if len(chat_history[channel_id]) > 15:
        chat_history[channel_id] = chat_history[channel_id][-15:]

    is_mentioned = bot.user in message.mentions
    is_dm = isinstance(message.channel, discord.DMChannel)

    if IS_CHAT_ENABLED and (is_mentioned or is_dm):
        await handle_chat_response(message, channel_id)
    
    await bot.process_commands(message)

@bot.event
async def on_guild_join(guild):
    print(f"🚀 Bot joined: {guild.name}")
    owner = await bot.fetch_user(OWNER_ID)
    if owner:
        try:
            await owner.send(f"GenA-Bot join server: **{guild.name}**\nID: `{guild.id}`")
        except:
            pass

async def handle_chat_response(message, channel_id):
    async with message.channel.typing():
        try:
            history = chat_history.get(channel_id, [])
            
            # Xác định System Prompt
            if IS_ROLEPLAY_ACTIVE and ACTIVE_ROLE_CONFIG:
                # Kết hợp Prompt của Role + Meta Prompt (để nhớ Owner/ID)
                system_instruction = f"{ACTIVE_ROLE_CONFIG['prompt']}\n\n{META_ROLEPLAY_PROMPT}"
            else:
                system_instruction = DEFAULT_SYSTEM_PROMPT

            # Xây dựng nội dung gửi lên API
            contents = [
                {
                    "role": "user",
                    "parts": [{"text": system_instruction}]
                },
                {
                    "role": "model",
                    "parts": [{"text": "Hiểu rồi. Bắt đầu thôi."}]
                }
            ]

            # Thêm lịch sử chat (Optimized: Chỉ gửi text sạch, hạn chế lặp lại ID rườm rà)
            for msg in history[:-1]: # Lấy tất cả trừ tin nhắn cuối (vì tin nhắn cuối xử lý riêng bên dưới)
                parts = []
                if msg.get('images'):
                    for img in msg['images']:
                        parts.append({
                            "inline_data": {"mime_type": img['mime_type'], "data": img['data']}
                        })
                
                # Format lịch sử gọn nhẹ: "Tên: Nội dung"
                parts.append({"text": f"{msg['user']}: {msg['content']}"})
                
                contents.append({
                    "role": "user",
                    "parts": parts
                })

            # Xử lý tin nhắn HIỆN TẠI (Tin nhắn cần trả lời)
            current_parts = []
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    try:
                        image_bytes = await attachment.read()
                        current_parts.append({
                            "inline_data": {"mime_type": attachment.content_type, "data": image_bytes}
                        })
                    except:
                        pass
            
            # Nhấn mạnh tin nhắn cuối cùng
            final_msg_text = f"[TIN NHẮN CẦN TRẢ LỜI] {message.author.display_name}: {message.content}"
            current_parts.append({"text": final_msg_text})
            
            contents.append({
                "role": "user",
                "parts": current_parts
            })

            model = get_model(DEFAULT_MODEL_ID)
            response = model.generate_content(contents)
            
            if response.text:
                await message.reply(response.text, mention_author=False)
            else:
                await message.reply("Bot đang suy nghĩ sâu xa quá nên kẹt cmnr 🥲", mention_author=False)
                
        except Exception as e:
            print(f"Lỗi API: {e}")
            await message.reply("Lỗi kết nối não bộ AI 🥲 Check log đi bro.", mention_author=False)

# --- SLASH COMMANDS ---

@bot.tree.command(name="model", description="Đổi model ID của bot")
@app_commands.describe(model_id="ID của model Gemini mới")
async def change_model(interaction: discord.Interaction, model_id: str):
    global DEFAULT_MODEL_ID
    DEFAULT_MODEL_ID = model_id
    await interaction.response.send_message(f"Đã đổi model sang: `{model_id}` 🔥", ephemeral=True)

@bot.tree.command(name="setting", description="Cài đặt bot (Owner Only)")
@app_commands.describe(
    action="Hành động",
    value="Giá trị tương ứng"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Xem cài đặt", value="view"),
    app_commands.Choice(name="Bật/Tắt Chat", value="toggle_chat"),
    app_commands.Choice(name="Đổi Max Tokens", value="set_tokens"),
    app_commands.Choice(name="Đổi Temperature", value="set_temp"),
])
async def setting_command(interaction: discord.Interaction, action: str, value: str = None):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Owner only nhen bẹn=))🥀", ephemeral=True)
        return

    global IS_CHAT_ENABLED, CURRENT_MAX_TOKENS, CURRENT_TEMPERATURE

    if action == "view":
        info = f"""
        **Cài đặt hiện tại:**
        - Model: `{DEFAULT_MODEL_ID}`
        - Chat Enabled: `{IS_CHAT_ENABLED}`
        - Roleplay Active: `{IS_ROLEPLAY_ACTIVE}`
        - Max Tokens: `{CURRENT_MAX_TOKENS}`
        - Temperature: `{CURRENT_TEMPERATURE}`
        """
        await interaction.response.send_message(info, ephemeral=True)
    elif action == "toggle_chat":
        IS_CHAT_ENABLED = not IS_CHAT_ENABLED
        status = "BẬT" if IS_CHAT_ENABLED else "TẮT"
        await interaction.response.send_message(f"Đã {status} tính năng chat 🔥", ephemeral=True)
    elif action == "set_tokens":
        if value and value.isdigit():
            CURRENT_MAX_TOKENS = int(value)
            await interaction.response.send_message(f"Max Tokens: `{value}` 🔥", ephemeral=True)
        else:
            await interaction.response.send_message("Nhập số đê bro!", ephemeral=True)
    elif action == "set_temp":
        if value:
            try:
                temp_val = float(value)
                if 0.0 <= temp_val <= 2.0:
                    CURRENT_TEMPERATURE = temp_val
                    await interaction.response.send_message(f"Temperature: `{temp_val}` 🔥", ephemeral=True)
                else:
                    await interaction.response.send_message("0.0 - 2.0 thôi bro!", ephemeral=True)
            except ValueError:
                await interaction.response.send_message("Số đê bro!", ephemeral=True)

@bot.tree.command(name="role_play", description="Bật chế độ nhập vai (Owner Only)")
@app_commands.describe(
    option="Chọn 'on' để bật, 'off' để tắt, hoặc 'sample' để xem mẫu",
    custom_prompt="Prompt nhập vai tùy chỉnh (chỉ dùng khi bật)"
)
@app_commands.choices(option=[
    app_commands.Choice(name="Bật (On)", value="on"),
    app_commands.Choice(name="Tắt (Off)", value="off"),
    app_commands.Choice(name="Xem mẫu (Sample)", value="sample"),
])
async def role_play_command(interaction: discord.Interaction, option: str, custom_prompt: str = None):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Owner only nhen bẹn=))🥀", ephemeral=True)
        return

    global IS_ROLEPLAY_ACTIVE, ACTIVE_ROLE_CONFIG

    if option == "off":
        IS_ROLEPLAY_ACTIVE = False
        ACTIVE_ROLE_CONFIG = None
        await interaction.response.send_message("Đã tắt chế độ Role Play. Về lại GenZ bình thường 😎", ephemeral=True)
        
    elif option == "sample":
        msg = "**Các Sample Role có sẵn:**\n"
        for key, val in SAMPLE_ROLES.items():
            msg += f"- **{key}**: {val['name']}\n"
        msg += "\n*Dùng lệnh này lại và paste prompt vào custom_prompt nếu muốn dùng sample.*"
        await interaction.response.send_message(msg, ephemeral=True)

    elif option == "on":
        if custom_prompt:
            # Nếu user tự nhập prompt
            ACTIVE_ROLE_CONFIG = {
                "name": "Custom Role",
                "prompt": custom_prompt
            }
            IS_ROLEPLAY_ACTIVE = True
            await interaction.response.send_message(f"Đã bật Role Play với prompt tùy chỉnh 🔥\n*Lưu ý: Meta prompt về Owner/ID đã được tự động thêm vào.*", ephemeral=True)
        else:
            await interaction.response.send_message("Vui lòng nhập prompt vào ô `custom_prompt` hoặc chọn sample để copy paste!", ephemeral=True)

# --- FLASK HEALTH CHECK ---
def run_flask():
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "Bot đang chạy ngon lành 🚀"

    @app.route('/health')
    def health():
        return "OK", 200
    
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    app.run(host='0.0.0.0', port=PORT)

def signal_handler(sig, frame):
    print('Đang tắt bot...')
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("Flask started. Running Discord Bot...")
    bot.run(DISCORD_TOKEN)