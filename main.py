import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Giữ bot sống (Koyeb cần mở port để ko bị sập)
app = Flask('')
@app.route('/')
def home():
    return "Bot đang gáy bẩn trên Google AI! 🥀"

def run():
    app.run(host='0.0.0.0', port=8080) # Koyeb thích port 8080 hơn

def keep_alive():
    t = Thread(target=run)
    t.start()

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)

# Prompt này bao trẩu, bao mất dạy cho m luôn 😇
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="M là Gemidờm - Bot Discord mất nết. Xưng m-t. Dùng teencode (ko, j, v, r, đc, bt, cx). Nết cục súc, hay khịa. Trả lời cực ngắn dưới 1 dòng. Nếu hỏi code/toán thì giải pro trong block code rồi chửi thêm câu."
)

chat_sessions = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user} nhập xác thành công! 💀')

@client.event
async def on_message(message):
    if message.author == client.user: return
    
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                user_id = str(message.author.id)
                if user_id not in chat_sessions:
                    chat_sessions[user_id] = model.start_chat(history=[])
                
                # Giới hạn token đầu ra cho đỡ tốn 
                response = chat_sessions[user_id].send_message(message.content)
                await message.reply(response.text)
            
            except Exception as e:
                print(f"Lỗi r: {e}")
                if user_id in chat_sessions: del chat_sessions[user_id]
                await message.reply("T chịu chết🥀💔")

keep_alive()
client.run(DISCORD_TOKEN)
