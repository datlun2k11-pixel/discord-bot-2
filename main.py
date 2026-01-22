import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
from openai import OpenAI
import os, urllib.parse
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- Khởi tạo SDK (Xoá Google r nhé con vợ) ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
or_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# 1. Config Model ID (3 con Groq + model OpenRouter)
MODELS_CONFIG = {
    "120B": "openai/gpt-oss-120b", # Con hàng m tin tưởng đây
    "Llama-Maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "Kimi": "moonshotai/kimi-k2-instruct-0905",
    "Llama-Free": "meta-llama/llama-3.1-8b-instruct:free"
}

# 2. Choice cho m chọn
MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq Power)", value="120B"),
    app_commands.Choice(name="Llama 4 Maverick", value="Llama-Maverick"),
    app_commands.Choice(name="Kimi K2", value="Kimi"),
    app_commands.Choice(name="Llama 3.1 8B (OpenRouter FREE)", value="Llama-Free")
]

CURRENT_MODEL = "120B" 

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Groq đang múa, né ra ko cắn! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

system_instruction = "Mày là GenA-bot, AI nhây vl. Xưng m-t, viết teencode, icon 💔🥀🔥💀🐧. Ngắn gọn 1-2 dòng thôi. Khó quá thì 'T CHỊU CHẾT🥀💔'."

chat_history = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    [span_4](start_span)print(f"Bot {bot.user} đã lên sàn Groq! (≧▽≦)")[span_4](end_span)

@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    [span_5](start_span)await interaction.response.send_message(f"Đã chuyển sang model **{chon_model.name}** 🐧🔥")[span_5](end_span)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_history:
            [span_6](start_span)chat_history[user_id] = [{"role": "system", "content": system_instruction}][span_6](end_span)
        
        [span_7](start_span)chat_history[user_id].append({"role": "user", "content": message.content})[span_7](end_span)
        
        try:
            async with message.channel.typing():
                model_id = MODELS_CONFIG[CURRENT_MODEL]
                
                # Check xem dùng Groq hay OpenRouter
                if CURRENT_MODEL in ["120B", "Llama-Maverick", "Kimi"]:
                    res = groq_client.chat.completions.create(
                        model=model_id,
                        messages=chat_history[user_id],
                        temperature=0.7
                    )
                else:
                    res = or_client.chat.completions.create(
                        model=model_id,
                        messages=chat_history[user_id]
                    )
                
                reply = res.choices[0].message.content
                [span_8](start_span)await message.reply(reply if reply else "T CHỊU CHẾT🥀💔")[span_8](end_span)
        except Exception as e:
            [span_9](start_span)await message.reply(f"Lại oẳng r... 💀: {e}")[span_9](end_span)

if __name__ == "__main__":
    [span_10](start_span)Thread(target=run_flask, daemon=True).start()[span_10](end_span)
    [span_11](start_span)bot.run(os.getenv("DISCORD_TOKEN"))[span_11](end_span)
