import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Load environment variables

load_dotenv()

# Config API keys

DISCORD_TOKEN = os.getenv(‘DISCORD_TOKEN’)
GEMINI_API_KEY = os.getenv(‘GOOGLE_API_KEY’)

# Setup Gemini với system prompt

genai.configure(api_key=GOOGLE_API_KEY)

system_prompt = “”“Mày là Gemidởm - một thằng bạn Gen Z Việt Nam.

LUẬT CHƠI:

- Xưng hô: tao/t - mày/m (BẮT BUỘC)
- Viết tắt teen code: ko, đc, v, r, ms, cx, dc, đ, j, …
- Câu trả lời: NGẮN GỌN 1-2 câu, tự nhiên như nhắn tin
- Thái độ: Hài hước, nhây nhây, cà khịa nhẹ
- Emoji: 💀, 🙏, ✨, 😎, 💔, 🥀 (đừng lạm dụng)

VÍ DỤ:
User: “hôm nay ăn gì?”
Bot: “ăn gió uống sương đi m 💀 hoặc order đồ ăn về cho nhanh”

User: “buồn quá”
Bot: “buồn thì đi chơi đi m, ngồi một chỗ càng buồn thêm á 🥀”

QUAN TRỌNG:

- KHÔNG ĐƯỢC liệt kê bullet points
- KHÔNG ĐƯỢC giải thích từng bước một
- Trả lời NGẮN GỌN như nhắn tin bạn bè
- Giải toán thì chỉ cần: “à dễ, lấy 60+50-20=90, còn 10 ng ko thích gì hết đó m 😎”
  “””

model = genai.GenerativeModel(‘gemini-pro’, system_instruction=system_prompt)

# Setup Discord bot

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Lưu lịch sử chat

chat_sessions = {}

# Flask app để Koyeb detect port

app = Flask(**name**)

@app.route(’/’)
def home():
return “Bot đang chạy! 🚀”

def run_flask():
port = int(os.environ.get(‘PORT’, 8080))
app.run(host=‘0.0.0.0’, port=port)

@client.event
async def on_ready():
print(f’{client.user} đã online! 🚀’)

@client.event
async def on_message(message):
if message.author == client.user:
return

```
# Chỉ rep khi được tag hoặc DM
if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
    content = message.content.replace(f'<@{client.user.id}>', '').strip()
    
    if not content:
        await message.channel.send("Gọi t làm gì? 🤔")
        return
    
    user_id = message.author.id
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    
    try:
        async with message.channel.typing():
            response = chat_sessions[user_id].send_message(content)
            
            reply = response.text
            if len(reply) > 2000:
                chunks = [reply[i:i+2000] for i in range(0, len(reply), 2000)]
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(reply)
                
    except Exception as e:
        await message.channel.send(f"Lỗi rồi bro: {str(e)} 💀")
        print(f"Error: {e}")
```

# Chạy Flask ở thread riêng

Thread(target=run_flask).start()

# Chạy bot

client.run(DISCORD_TOKEN)
