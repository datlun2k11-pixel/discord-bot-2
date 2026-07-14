import discord
import json
import os
import threading
from collections import deque

# Thread lock for file operations
file_lock = threading.Lock()

# Channel memory: stores last 15 messages per channel
CHANNEL_MEMORY = {}

def load_json(filepath, default):
    """Load JSON file with error handling for corrupted files."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is corrupted, return default and create new file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2)
        return default

def save_json(filepath, data):
    """Save JSON file with thread lock to prevent race conditions."""
    with file_lock:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def load_channel_memory():
    """Load channel memory from file."""
    global CHANNEL_MEMORY
    data = load_json('channel_memory.json', {})
    for channel_id, messages in data.items():
        CHANNEL_MEMORY[channel_id] = deque(messages, maxlen=15)

def save_channel_memory():
    """Save channel memory to file."""
    data = {ch_id: list(messages) for ch_id, messages in CHANNEL_MEMORY.items()}
    save_json('channel_memory.json', data)

def load_chat_history():
    """Load chat history with limit to prevent memory leak."""
    data = load_json('chat_history.json', {})
    # Limit to 50 Q/A pairs per user to prevent memory leak
    for user_id in data:
        if len(data[user_id]) > 50:
            data[user_id] = data[user_id][-50:]
    return data

def save_chat_history(history):
    """Save chat history."""
    save_json('chat_history.json', history)

async def setup_event(tree, config):
    @tree.event
    async def on_ready():
        print(f'✅ Bot đã online với tên: {tree.bot.user}')
        load_channel_memory()
        try:
            synced = await tree.sync()
            print(f'✅ Đã sync {len(synced)} commands')
        except Exception as e:
            print(f'❌ Lỗi sync: {e}')
    
    @tree.event
    async def on_message(message):
        # Ignore bot messages
        if message.author.bot:
            return
        
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)
        
        # Update channel memory
        if channel_id not in CHANNEL_MEMORY:
            CHANNEL_MEMORY[channel_id] = deque(maxlen=15)
        
        CHANNEL_MEMORY[channel_id].append({
            'author': message.author.display_name,
            'author_id': user_id,
            'content': message.content,
            'timestamp': message.created_at.isoformat()
        })
        
        # Save channel memory periodically
        save_channel_memory()
        
        # Anti-spam check
        if hasattr(message.author, 'last_message_time'):
            import time
            if time.time() - message.author.last_message_time < 30:
                message.author.spam_count = getattr(message.author, 'spam_count', 0) + 1
                if message.author.spam_count >= 3:
                    await message.channel.send(f"{message.author.mention} ⚠️ Đừng spam!")
                    return
            else:
                message.author.spam_count = 0
        message.author.last_message_time = __import__('time').time()
        
        # Check if bot is mentioned
        if tree.bot.user in message.mentions:
            # Build prompt with context
            context_messages = list(CHANNEL_MEMORY.get(channel_id, []))
            context_text = "\n".join([f"{m['author']}: {m['content']}" for m in context_messages])
            
            # Load chat history
            chat_history = load_chat_history()
            if user_id not in chat_history:
                chat_history[user_id] = []
            
            # Build system prompt
            system_prompt = f"Mày là Qwen GenZ, một thằng bạn thân online. Nói chuyện hài hước, nhây, cà khịa nhẹ.\n\nContext chat gần đây:\n{context_text}"
            
            # Build conversation history
            conversation = []
            for qa in chat_history[user_id][-10:]:  # Last 10 Q/A pairs
                conversation.append({'role': 'user', 'parts': [qa['question']]})
                conversation.append({'role': 'model', 'parts': [qa['answer']]})
            
            # Add current message
            conversation.append({'role': 'user', 'parts': [message.content]})
            
            try:
                # Generate response using Gemini
                model = config['model']
                response = await model.generate_content_async(
                    [system_prompt] + conversation,
                    generation_config={
                        'max_output_tokens': 500,
                        'temperature': 0.7
                    }
                )
                
                reply = response.text
                
                # Save to chat history
                chat_history[user_id].append({
                    'question': message.content,
                    'answer': reply
                })
                
                # Limit history size to prevent memory leak
                if len(chat_history[user_id]) > 50:
                    chat_history[user_id] = chat_history[user_id][-50:]
                
                save_chat_history(chat_history)
                
                await message.reply(reply)
            except Exception as e:
                await message.reply(f"❌ Lỗi: {e}")
