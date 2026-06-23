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

# Load biến môi trường
load_dotenv()

# --- CẤU HÌNH GLOBAL (M SỬA Ở ĐÂY) ---
PORT = int(os.getenv('PORT', 8080))
DEFAULT_MODEL_ID = "gemini-3.1-flash-lite"
OWNER_ID = 1155129530122510376

# Thông số mặc định cho Gemini
CURRENT_MAX_TOKENS = 2048
CURRENT_TEMPERATURE = 0.9
IS_CHAT_ENABLED = True

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Cấu hình Google Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Cấu hình Discord Bot
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Lưu trữ history chat cho từng kênh: {channel_id: [list_of_messages]}
chat_history = {}

# System Prompt mới nhất
SYSTEM_PROMPT = """
Mày là 1 con AI Discord, tên là GenA-Bot (UserID:<@1458799287910535324>), bạn thân online của user. Owner của mày có userID: <@1155129530122510376>.

TÍNH CÁCH: Hài hước, nhây, cà khịa, toxic vui, trêu đùa nhẹ, xin lỗi khi làm user thất vọng nói chung là ko toxic quá nặng lời, nói chuyện tự nhiên như Gen Z thật. Nói chuyện ngắn gọn (1-2 dòng) cho duyên dáng.
CÁCH NÓI: Xưng hô "m - t" hoặc "bro". Dùng teencode vừa phải (ko, cx, v, j, bít, r, th…). 
Thỉnh thoảng chèn emoji 💀, 🔥, 🥀, 🐧, 😇, 🥹,... và emoticon/kaomoji nhưng đừng spam. 
Joke style: Ví dụ "ko đi bằng chân thì m đi bằng đầu à".

QUY TẮC XỬ LÝ CHATLOG (CỰC KỲ QUAN TRỌNG):
1. Chatlog bên dưới chỉ là BỐI CẢNH (Context) để m hiểu tình hình, KHÔNG PHẢI là câu hỏi cần trả lời.
2. M CHỈ ĐƯỢC PHẢN HỒI lại tin nhắn CUỐI CÙNG của người đã TAG hoặc DM m.
3. Tuyệt đối ko được chửi bới hay phản hồi vào các tin nhắn cũ ở đầu hoặc giữa chatlog.
4. Nếu tin nhắn cuối cùng chỉ là tag suông, hãy chào hỏi hoặc hỏi xem m cần gì.
"""

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
    # Đồng bộ lệnh Slash Command
    try:
        synced = await bot.tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh.")
    except Exception as e:
        print(f"Lỗi đồng bộ lệnh: {e}")

@bot.event
async def on_message(message):
    # Bỏ qua tin nhắn của chính bot
    if message.author == bot.user:
        return

    channel_id = message.channel.id
    
    # Cập nhật history cho kênh này
    if channel_id not in chat_history:
        chat_history[channel_id] = []
    
    # Thêm tin nhắn mới vào history
    chat_history[channel_id].append({
        'user': f"{message.author.display_name} (ID: {message.author.id})",
        'content': message.content
    })

    # Giữ lại tối đa 15 tin nhắn gần nhất
    if len(chat_history[channel_id]) > 15:
        chat_history[channel_id] = chat_history[channel_id][-15:]

    # Kiểm tra xem bot có được tag hoặc DM không VÀ tính năng chat đang bật
    is_mentioned = bot.user in message.mentions
    is_dm = isinstance(message.channel, discord.DMChannel)

    if IS_CHAT_ENABLED and (is_mentioned or is_dm):
        await handle_chat_response(message, channel_id)
    
    # Xử lý lệnh cũ nếu có
    await bot.process_commands(message)
@bot.event
async def on_guild_join(guild):
    print(f"🚀 Bot đã tham gia server: {guild.name} (ID: {guild.id})")
    # Nếu m muốn gửi thông báo về DM của owner thì dùng thêm:
    owner = await bot.fetch_user(OWNER_ID)
    if owner:
        try:
            await owner.send(f"GenA-Bot vừa join server: **{guild.name}**\nID: `{guild.id}`\nThành viên: {guild.member_count}")
        except:
            pass # Bỏ qua nếu owner block DM hoặc lỗi gì đó
async def handle_chat_response(message, channel_id):
    async with message.channel.typing():
        try:
            history = chat_history.get(channel_id, [])
            
            # Chuẩn bị nội dung gửi lên API
            prompt_parts = [SYSTEM_PROMPT + "\n\nLịch sử chat gần đây:\n"]
            for msg in history:
                prompt_parts.append(f"{msg['user']}: {msg['content']}")
            
            # Xử lý tin nhắn hiện tại (có thể kèm ảnh)
            current_content = [{"text": f"\n{message.author.display_name} (ID: {message.author.id}): {message.content}"}]
            
            # Nếu có ảnh đính kèm thì tải về và thêm vào prompt
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        try:
                            image_bytes = await attachment.read()
                            current_content.append({
                                "inline_data": {
                                    "mime_type": attachment.content_type,
                                    "data": image_bytes
                                }
                            })
                        except Exception as img_err:
                            print(f"Lỗi tải ảnh: {img_err}")
            
            prompt_parts.append(current_content)
            
            model = get_model(DEFAULT_MODEL_ID)
            response = model.generate_content(prompt_parts)
            
            if response.text:
                await message.channel.send(
                    response.text, 
                    reference=message,
                    mention_author=False
                )
            else:
                await message.channel.send("Bot không nghĩ ra câu trả lời nào hợp lệ 🥲", reference=message)
                
        except Exception as e:
            print(f"Lỗi khi gọi API: {e}")
            await message.channel.send("Đm, lỗi cmnr 🥲 Check log đi bro.", reference=message)
# --- SLASH COMMANDS ---

@bot.tree.command(name="model", description="Đổi model ID của bot")
@app_commands.describe(model_id="ID của model Gemini mới")
async def change_model(interaction: discord.Interaction, model_id: str):
    global DEFAULT_MODEL_ID
    DEFAULT_MODEL_ID = model_id
    await interaction.response.send_message(f"Đã đổi model sang: `{model_id}` 🔥", ephemeral=True)
@bot.tree.command(name="servers", description="Xem danh sách server bot đang ở (Owner Only)")
async def list_servers(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Cút đi, lệnh này dành cho owner thôi 😤", ephemeral=True)
        return
    
    guilds = bot.guilds
    if not guilds:
        await interaction.response.send_message("Bot chưa join server nào cả 🥲", ephemeral=True)
        return

    msg = "**Danh sách server GenA-Bot đang ở:**\n"
    for g in guilds:
        msg += f"- {g.name} (ID: {g.id}) | Members: {g.member_count}\n"
    
    # Discord có giới hạn độ dài tin nhắn, nếu nhiều quá thì cắt bớt hoặc gửi file
    if len(msg) > 2000:
        msg = msg[:1990] + "..."
        
    await interaction.response.send_message(msg, ephemeral=True)
@bot.tree.command(name="setting", description="Cài đặt bot (Owner Only)")
@app_commands.describe(
    action="Hành động: view, toggle_chat, set_tokens, set_temp",
    value="Giá trị tương ứng (nếu cần)"
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
        - Max Tokens: `{CURRENT_MAX_TOKENS}`
        - Temperature: `{CURRENT_TEMPERATURE}`
        - Owner ID: `{OWNER_ID}`
        """
        await interaction.response.send_message(info, ephemeral=True)

    elif action == "toggle_chat":
        IS_CHAT_ENABLED = not IS_CHAT_ENABLED
        status = "BẬT" if IS_CHAT_ENABLED else "TẮT"
        await interaction.response.send_message(f"Đã {status} tính năng chat 🔥", ephemeral=True)

    elif action == "set_tokens":
        if not value or not value.isdigit():
            await interaction.response.send_message("Vui lòng nhập số tokens hợp lệ!", ephemeral=True)
            return
        CURRENT_MAX_TOKENS = int(value)
        await interaction.response.send_message(f"Đã đổi Max Tokens thành: `{value}` 🔥", ephemeral=True)

    elif action == "set_temp":
        if not value:
            await interaction.response.send_message("Vui lòng nhập giá trị temperature (0.0 - 2.0)!", ephemeral=True)
            return
        try:
            temp_val = float(value)
            if 0.0 <= temp_val <= 2.0:
                CURRENT_TEMPERATURE = temp_val
                await interaction.response.send_message(f"Đã đổi Temperature thành: `{temp_val}` 🔥", ephemeral=True)
            else:
                await interaction.response.send_message("Temperature phải nằm trong khoảng 0.0 đến 2.0!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Giá trị không hợp lệ!", ephemeral=True)

# --- FLASK HEALTH CHECK ---
def run_flask():
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "Bot đang chạy ngon lành 🚀"

    @app.route('/health')
    def health():
        return "OK", 200
    
    # Disable logs để console sạch hơn trên Koyeb
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

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("Flask đã khởi động, đang chạy Discord Bot...")
    # Run Discord Bot
    bot.run(DISCORD_TOKEN)