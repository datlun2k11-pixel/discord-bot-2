import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo (Koyeb)
app = Flask('')
@app.route('/')
def home():
    return "Gemidờm Google - Đã nạp full muối! 🥀"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') # Nhớ đổi tên trong .env nha m

# Setup Google Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Config cho nó "bay"
generation_config = {
  "temperature": 1.0, # Tăng độ sáng tạo/nhây
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 2000,
}

# System Prompt siêu mất nết
system_instruction = """
Mày là Gemidờm - Bot Discord báo đời. 
1. Xưng hô: Tao (t) - Mày (m). CẤM xưng tôi/bạn/em/anh.
2. Ngôn ngữ: Dùng Teencode nặng đô (ko, j, v, r, đc, bt, h, ntn, cx, ms...).
3. Thái độ: Cục súc, mỏ hỗn, hài hước, hay khịa người dùng.
4. Trả lời: Ngắn gọn (dưới 1-2 dòng) cho các câu hỏi thường.
5. Icon: Dùng nhiều icon vô tri (🥀, 🐧, 💀, 😇, 💔).
6. NGOẠI LỆ: Nếu user hỏi code, toán, kiến thức -> Trả lời nghiêm túc, chính xác, dài dòng trong block code, nhưng mở đầu và kết thúc vẫn phải chửi hoặc khịa.
"""

# Chọn model: gemini-1.5-flash (nhanh, free) hoặc gemini-2.0-flash-exp (nếu có)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=system_instruction
)

# Bộ nhớ chat (lưu tạm trong RAM)
chat_sessions = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã nhập xác Gemini! (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                user_id = message.author.id
                
                # Tạo session chat mới nếu chưa có
                if user_id not in chat_sessions:
                    chat_sessions[user_id] = model.start_chat(history=[])
                
                chat = chat_sessions[user_id]
                
                # Gửi tin nhắn cho Gemini
                response = chat.send_message(message.content)
                reply = response.text
                
                await message.reply(reply)
            
            except Exception as e:
                print(f"Lỗi: {e}")
                # Reset chat nếu lỗi history quá dài hoặc lỗi 400
                if user_id in chat_sessions:
                    del chat_sessions[user_id]
                await message.reply(f"Lỗi r, t reset não cái nha m 💀 (Lỗi: {e})")

keep_alive()
client.run(DISCORD_TOKEN)
