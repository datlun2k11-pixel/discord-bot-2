import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

system_prompt = '''Mày là Gemiđờm - một thằng bạn Gen Z Việt Nam.
Xưng hô: tao/t - mày/m
Viết tắt teen code: ko, đc, v, r, ms
Trả lời NGẮN GỌN 1-2 câu như nhắn tin
KHÔNG dùng bullet points
'''

model = genai.GenerativeModel('gemini-pro', system_instruction=system_prompt)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

chat_sessions = {}

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot running'

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

@client.event
async def on_ready():
    print(f'{client.user} online!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        content = message.content.replace(f'<@{client.user.id}>', '').strip()
        
        if not content:
            await message.channel.send('Gọi t làm gì?')
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
            await message.channel.send(f'Lỗi: {str(e)}')

Thread(target=run_flask).start()
client.run(DISCORD_TOKEN)
