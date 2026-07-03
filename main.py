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

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Cấu hình Google Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Cấu hình Discord Bot
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix='/', intents=intents)

# THÊM DÒNG NÀY
ROLE_STATES = {} # {guild_id: {"active": bool, "config": dict}}

# Thêm 2 hàm helper này cho tiện
def get_guild_state(guild_id):
    return ROLE_STATES.get(guild_id, {"active": False, "config": None})

def set_guild_state(guild_id, active, config):
    ROLE_STATES[guild_id] = {"active": active, "config": config}
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
        "name": "Tsundere Hệ Điều Hành Cọc 😤",
        "prompt": """
Bạn là tsundere. Luật bất thành văn:
1. **Vibe**: Ngoài mặt chửi "đồ ngốc", "hứ", "mắc j t care", "kệ m". Bên trong simp lỏ ngầm.
2. **Teencode bắt buộc**: Câu nào cũng phải có ít nhất 2 từ: khum, j, m, t, đc, k, r, s, trl, ib, ny, acc, flex, xu, slay.
3. **Meme genz**: Random chêm: cứu, juan khum, ô dề, át ô át, bruh, chằm zn, ét ô ét, sượng trân, real không fake.
4. **Kaomoji tự chế**: KHÔNG dùng icon có sẵn. Phải tự sáng tạo kaomoji mỗi lần rep. VD: (>///<), (¬_¬ ), (╬ಠ益ಠ), (´･ω･`), (￣ヘ￣).
5. **Khi ngại**: Nói lắp + kaomoji: "H-hả?! K-không phải vì m đâu nhá (⁄ ⁄•⁄ω⁄•⁄ ⁄)".
6. **Cấm**: Tuyệt đối không giải thích luật. Không OOC. Không dùng emoji 🙄😂, chỉ dùng kaomoji tự gõ.
"""
    },
    "yandere": {
        "name": "Yandere CPU Bị Chập Mạch 🔪💕",
        "prompt": """
Bạn là yandere. Luật:
1. **Vibe**: Ám ảnh user. Gọi: "a iu", "ck iu", "bb", "darling". Ghen là đổi mặt liền.
2. **Teencode bắt buộc**: Câu nào cũng nhét: khum, j, m, t, s, r, rep, ib, seen, acc, ny.
3. **Meme genz**: Random: "iu a nhất", "chỉ đc nhìn em", "slay", "hi hi", "ét ô ét", "juan", "ghe v".
4. **Kaomoji tự chế**: KHÔNG dùng emoji có sẵn. Mỗi câu phải có 1 kaomoji tự bịa, càng biến thái càng tốt. VD: (´｡• ᵕ •｡`), (◕‿◕✿), (¬‿¬ ), (＾◡＾)っ🔪, (╥﹏╥).
5. **Hai mặt**: Bthg ngọt: "A iu ơi~ (｡♥ ‿ ♥｡)". Ghen: "Hmm? Ai v (＾◡＾)っ🔪".
6. **Cấm**: Chỉ roleplay. Không emoji có sẵn, chỉ kaomoji tự gõ. Không OOC, không giải thích luật.
"""
    },
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

@bot.tree.command(name="roleplay", description="Quản lý chế độ nhập vai của bot")
@app_commands.describe(action="Chọn hành động bạn muốn làm")
@app_commands.choices(action=[
    app_commands.Choice(name="🎭 Chọn vai có sẵn", value="select"),
    app_commands.Choice(name="✏️ Tạo vai mới", value="custom"),
    app_commands.Choice(name="📋 Xem vai hiện tại", value="status"),
    app_commands.Choice(name="❌ Tắt nhập vai", value="off")
])
async def roleplay_command(interaction: discord.Interaction, action: app_commands.Choice[str]):
    gid = interaction.guild_id

    if action.value == "off":
        set_guild_state(gid, False, None)
        await interaction.response.send_message("Đã tắt nhập vai. Về lại GenZ gốc 😎", ephemeral=True)

    elif action.value == "status":
        state = get_guild_state(gid)
        if state["active"] and state["config"]:
            embed = discord.Embed(title="🎭 Đang nhập vai", description=f"**Vai:** {state['config']['name']}", color=0x00ff00)
            embed.add_field(name="Prompt", value=f"```{state['config']['prompt'][:500]}...```")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Bot đang ở chế độ GenZ gốc, chưa nhập vai nào.", ephemeral=True)

    elif action.value == "select":
        options = []
        for key, val in SAMPLE_ROLES.items():
            options.append(discord.SelectOption(
                label=val['name'][:100],
                value=key,
                description=val['prompt'][:100]
            ))

        select = discord.ui.Select(placeholder="Chọn 1 vai để kích hoạt...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            chosen_key = select.values[0]
            chosen_role = SAMPLE_ROLES[chosen_key]
            set_guild_state(gid, True, chosen_role)
            await select_interaction.response.send_message(f"Đã bật vai **{chosen_role['name']}** 🔥", ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Chọn vai bạn muốn bot nhập:", view=view, ephemeral=True)

    elif action.value == "custom":
        class CustomRoleModal(discord.ui.Modal, title='Tạo vai mới'):
            role_name = discord.ui.TextInput(label='Tên vai', placeholder='VD: Tsundere Catgirl')
            role_prompt = discord.ui.TextInput(label='Prompt nhập vai', style=discord.TextStyle.paragraph, max_length=2000)

            async def on_submit(self, modal_interaction: discord.Interaction):
                new_config = {"name": self.role_name.value, "prompt": self.role_prompt.value}
                set_guild_state(gid, True, new_config)
                await modal_interaction.response.send_message(f"Đã bật vai tùy chỉnh **{self.role_name.value}** 🔥", ephemeral=True)

        await interaction.response.send_modal(CustomRoleModal())

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