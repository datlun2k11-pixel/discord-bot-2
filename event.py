import time
import json
import os
import tempfile
import shutil
from collections import deque
from typing import Dict, Optional
import discord
import config

# --- BỘ NHỚ THÔNG MINH CHO KOYEB ---
# CHANNEL_MEMORY: lưu 15 tin nhắn gần nhất mỗi channel
# Cấu trúc: {channel_id: deque(maxlen=15)}
CHANNEL_MEMORY: Dict[int, deque] = {}

# File lưu memory (để khi restart bot vẫn nhớ)
MEMORY_FILE = "channel_memory.json"

def load_memory():
    """Load memory từ file JSON khi bot khởi động"""
    global CHANNEL_MEMORY
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for channel_id_str, messages in data.items():
                channel_id = int(channel_id_str)
                CHANNEL_MEMORY[channel_id] = deque(messages, maxlen=15)
            print(f"✅ Đã load memory cho {len(CHANNEL_MEMORY)} channel")
        except Exception as e:
            print(f"⚠️ Lỗi load memory: {e}")

def save_memory():
    """Lưu memory ra file JSON (atomic write)"""
    try:
        data = {}
        for channel_id, messages in CHANNEL_MEMORY.items():
            data[str(channel_id)] = list(messages)
        
        # Atomic write: ghi vào temp file trước, rename sau
        temp_fd, temp_path = tempfile.mkstemp(dir=".")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(temp_path, MEMORY_FILE)
        except Exception:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise
    except Exception as e:
        print(f"⚠️ Lỗi save memory: {e}")

def get_channel_context(channel_id: int, max_messages: int = 15) -> str:
    """Lấy context chat của channel (tối đa 15 tin)"""
    if channel_id not in CHANNEL_MEMORY:
        CHANNEL_MEMORY[channel_id] = deque(maxlen=15)
        return "Chưa có tin nhắn nào trong channel này."
    
    history = list(CHANNEL_MEMORY[channel_id])
    if not history:
        return "Chưa có tin nhắn nào trong channel này."
    
    # Lấy 15 tin gần nhất (hoặc ít hơn)
    recent = history[-max_messages:]
    context = "\n".join(recent)
    return context

def format_message_for_memory(msg: discord.Message) -> str:
    """Format tin nhắn để lưu vào memory (ngắn gọn, tiết kiệm token)"""
    author_name = msg.author.display_name or msg.author.name
    
    # Xử lý nội dung tin nhắn
    content = msg.content or ""
    # Nếu tin nhắn chỉ có ảnh/sticker
    if not content and msg.attachments:
        content = "[📷 Ảnh]"
    elif not content and msg.stickers:
        content = "[🎨 Sticker]"
    elif not content:
        content = "[💬 Tin nhắn trống]"
        
    # Cắt ngắn nội dung nếu quá dài (tiết kiệm token)
    if len(content) > 200:
        content = content[:197] + "..."
        
    # Xử lý reply (quan trọng để hiểu ngữ cảnh)
    reply_context = ""
    if msg.reference and msg.reference.resolved:
        replied = msg.reference.resolved
        if isinstance(replied, discord.Message):
            replied_name = replied.author.display_name or replied.author.name
            replied_content = replied.content or "[📷 Ảnh]"
            if len(replied_content) > 50:
                replied_content = replied_content[:47] + "..."
            reply_context = f" (→ {replied_name}: {replied_content})"
            
    return f"{author_name}: {content}{reply_context}"

# === KIỂM TRA DAILY LIMIT ===
async def _check_daily_limit_and_reply(message: discord.Message) -> bool:
    """Kiểm tra daily limit, trả về True nếu còn lượt, False nếu hết"""
    user_id = message.author.id
    # Owner không bị giới hạn
    if user_id == config.OWNER_ID:
        return True
    
    has_remaining, remaining = config.check_daily_limit(user_id)
    if not has_remaining:
        embed = discord.Embed(
            title="😴 Hết lượt chat hôm nay rồi!",
            description=(
                f"Bạn đã dùng hết **{config.DAILY_LIMIT_PER_USER}** lượt chat với bot hôm nay rồi! 🥀\n\n"
                f"Quay lại vào ngày mai nha! ⏰\n"
                f"(Lượt sẽ reset lúc **0:00** theo giờ Việt Nam)"
            ),
            color=0xFFA500,
        )
        embed.set_footer(text="=)) chat ít thôi để còn lượt nha bro")
        await message.reply(embed=embed, mention_author=False)
        return False
    return True

# --- HÀM ON_MESSAGE NÂNG CẤP (TỐI ƯU CHO KOYEB) ---
def register_events(bot):
    @bot.event
    async def on_ready():
        print(f"Bot đã đăng nhập với tên: {bot.user.name}")
        print(f"Default Model: {config.DEFAULT_MODEL_ID}")
        # Load memory từ file
        load_memory()
        try:
            synced = await bot.tree.sync()
            print(f"Đã đồng bộ {len(synced)} lệnh.")
        except Exception as error:
            print(f"Lỗi đồng bộ lệnh: {error}")

    @bot.event
    async def on_guild_join(guild: discord.Guild):
        try:
            owner = await bot.fetch_user(config.OWNER_ID)
            if not owner:
                return
            invite_url = await _build_invite_url(guild)
            if not invite_url:
                invite_url = "https://discord.gg/invalid"
            embed = discord.Embed(
                title="✅ Bot vừa join 1 server mới!",
                color=0x00F0FF,
                description=(
                    f"**Server:** {guild.name}\n"
                    f"**ID:** {guild.id}\n"
                    f"**Số thành viên:** {guild.member_count}\n\n"
                    f"**Link:** [Vào server]({invite_url})"
                ),
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else "")
            await owner.send(embed=embed)
        except Exception as error:
            print(f"Lỗi gửi DM khi join server: {error}")

    @bot.event
    async def on_message(message: discord.Message):
        # Bỏ qua tin nhắn của bot và lệnh
        if message.author == bot.user or message.content.startswith("/"):
            await bot.process_commands(message)
            return

        # --- 1. LƯU TIN NHẮN VÀO MEMORY (LUÔN LUÔN) ---
        if message.guild:
            channel_id = message.channel.id
            # Khởi tạo memory cho channel nếu chưa có
            if channel_id not in CHANNEL_MEMORY:
                CHANNEL_MEMORY[channel_id] = deque(maxlen=15)
            
            # Format và lưu tin nhắn
            formatted = format_message_for_memory(message)
            CHANNEL_MEMORY[channel_id].append(formatted)
            
            # Cập nhật thống kê
            guild_id = message.guild.id
            config.MSG_COUNTERS[guild_id] = config.MSG_COUNTERS.get(guild_id, 0) + 1
            
            # Lưu memory sau mỗi 20 tin nhắn (giảm I/O, tối ưu cho Koyeb)
            if len(CHANNEL_MEMORY[channel_id]) % 20 == 0:
                save_memory()
            
        # --- 2. KIỂM TRA CÓ CẦN REPLY KHÔNG ---
        is_dm = message.guild is None
        is_reply_to_bot = (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == bot.user
        )
        is_mentioned = bot.user in message.mentions
        
        # Nếu không tag, không reply, không DM -> không xử lý
        if not is_dm and not is_mentioned and not is_reply_to_bot:
            return
            
        # Check guild-specific chat_enabled (nếu server đã cài đặt)
        if message.guild:
            guild_settings = config.GUILD_SETTINGS.get(str(message.guild.id), {})
            if guild_settings.get("chat_enabled") is False:
                return
        elif not config.IS_CHAT_ENABLED:
            return

        # === KIỂM TRA DAILY LIMIT ===
        if not await _check_daily_limit_and_reply(message):
            return

        # --- 3. ANTI-SPAM (GIỮ NGUYÊN) ---
        now = time.time()
        user_id = message.author.id
        if user_id != config.OWNER_ID:
            if user_id not in config.SPAM_TRACKER:
                config.SPAM_TRACKER[user_id] = {
                    "last_msgs": [],
                    "blocked_until": 0,
                    "last_content": "",
                    "dup_count": 0,
                }
            user_spam_data = config.SPAM_TRACKER[user_id]
            
            if now < user_spam_data["blocked_until"]:
                return
                
            is_duplicate = (
                message.content == user_spam_data["last_content"]
                and (now - user_spam_data.get("last_time", 0) < 10)
            )
            
            if is_duplicate:
                user_spam_data["dup_count"] += 1
            else:
                user_spam_data["dup_count"] = 1
                
            user_spam_data["last_content"] = message.content
            user_spam_data["last_time"] = now
            
            user_spam_data["last_msgs"] = [
                timestamp for timestamp in user_spam_data["last_msgs"]
                if now - timestamp < 7
            ]
            user_spam_data["last_msgs"].append(now)
            
            hit_rate_limit = (
                len(user_spam_data["last_msgs"]) > 5
                or user_spam_data["dup_count"] >= 4
            )
            
            if hit_rate_limit:
                user_spam_data["blocked_until"] = now + 30
                user_spam_data["last_msgs"] = []
                user_spam_data["dup_count"] = 0
                await message.channel.send(
                    f"<@{user_id}> Spam clm, cút 30s! 🤡",
                    delete_after=10,
                )
                return

        # --- 4. XÂY DỰNG CONTEXT CHO AI ---
        ctx_key = config.get_context_key(message)
        state = config.get_context_state(ctx_key)
        
        # System prompt
        if state["active"]:
            system_instruction = f"{state['config']['prompt']}\n\n{config.META_ROLEPLAY_PROMPT}"
        else:
            system_instruction = config.DEFAULT_SYSTEM_PROMPT

        # --- 5. XỬ LÝ ẢNH (GIỮ NGUYÊN) ---
        image_parts = []
        for attachment in message.attachments:
            is_image = attachment.content_type and attachment.content_type.startswith("image/")
            if not is_image:
                continue
            try:
                image_bytes = await attachment.read()
                image_parts.append(
                    {"mime_type": attachment.content_type, "data": image_bytes}
                )
            except Exception:
                pass

        # --- 6. TẠO PROMPT THÔNG MINH (TỐI ƯU TOKEN) ---
        try:
            async with message.channel.typing():
                # Sử dụng guild-specific settings nếu có
                if message.guild:
                    guild_settings = config.GUILD_SETTINGS.get(str(message.guild.id), {})
                    g_max_tokens = guild_settings.get("max_tokens", config.DEFAULT_MAX_TOKENS)
                    g_temperature = guild_settings.get("temperature", config.DEFAULT_TEMPERATURE)
                    model = config.get_model_for_guild(g_max_tokens, g_temperature)
                else:
                    model = config.get_model(config.CURRENT_MODEL_ID)
                clean_content = config.strip_bot_mention(
                    message.content,
                    bot.user.id if bot.user else None,
                )
                
                # Lấy thông tin user
                author_name = message.author.display_name or message.author.name
                
                # Lấy context từ channel memory (15 tin gần nhất)
                channel_context = get_channel_context(message.channel.id, max_messages=15)
                
                # Lấy lịch sử chat cũ (để bot nhớ tương tác trước đó)
                if ctx_key not in config.chat_history:
                    config.chat_history[ctx_key] = []
                old_history = config.chat_history[ctx_key]
                
                old_history_text = ""
                if old_history:
                    history_lines = []
                    for item in old_history[-10:]:  # Chỉ lấy 10 tin cuối để tiết kiệm token
                        if item["role"] == "user":
                            name = item.get("display_name", "User")
                            history_lines.append(f"{name}: {item['parts'][0]}")
                        else:
                            history_lines.append(f"Bot: {item['parts'][0]}")
                    old_history_text = "\n".join(history_lines)

                # Kiểm tra reply
                reply_info = ""
                if message.reference and message.reference.resolved:
                    replied = message.reference.resolved
                    if isinstance(replied, discord.Message):
                        replied_name = replied.author.display_name or replied.author.name
                        replied_content = replied.content or "[không có text]"
                        if len(replied_content) > 100:
                            replied_content = replied_content[:97] + "..."
                        reply_info = f"\n[💬 {author_name} đang trả lời {replied_name}: \"{replied_content}\"]"

                # --- TẠO PROMPT CHUẨN (TỐI ƯU) ---
                prompt_parts = [system_instruction]
                
                # Context từ channel (QUAN TRỌNG: 15 tin gần nhất)
                prompt_parts.append("\n--- LỊCH SỬ CHAT 15 TIN GẦN NHẤT ---")
                prompt_parts.append(channel_context)
                
                # Context từ tương tác cũ với bot (nếu có)
                if old_history_text:
                    prompt_parts.append("\n--- LỊCH SỬ TƯƠNG TÁC CŨ ---")
                    prompt_parts.append(old_history_text)
                
                # Thông tin reply
                if reply_info:
                    prompt_parts.append(reply_info)
                
                # Tin nhắn hiện tại
                prompt_parts.append(f"\n--- TIN NHẮN CỦA {author_name.upper()} ---")
                prompt_parts.append(clean_content)
                
                # Hướng dẫn cuối
                if message.reference and message.reference.resolved:
                    prompt_parts.append("\n⚠️ LƯU Ý: Tin nhắn này đang reply người khác. Hãy trả lời phù hợp với ngữ cảnh!")
                
                prompt_parts.append("\nTrả lời ngắn gọn, hài hước, đúng phong cách GenZ.")
                
                # Thêm ảnh nếu có
                if image_parts:
                    prompt_parts.extend(image_parts)

                # --- GỌI API ---
                response = await model.generate_content_async(prompt_parts)
                response_text = config.extract_response_text(response)
                
                if not response_text:
                    response_text = "T bị câm ngang API r, nói lại phát 💀"
                    
                response_text = response_text[:2000].strip()

                # --- GỬI REPLY ---
                if config.has_avatar_tag(response_text):
                    response_text = config.remove_avatar_tag(response_text)
                    if not response_text:
                        response_text = "🥀"
                    if bot.user.avatar:
                        embed = discord.Embed(color=0x00F0FF)
                        embed.set_image(url=bot.user.avatar.url)
                        await message.reply(
                            response_text if response_text else "🥀",
                            embed=embed,
                            mention_author=False,
                        )
                    else:
                        await message.reply(
                            response_text if response_text else "Hồn nhiên t khum có avatar 💀",
                            mention_author=False,
                        )
                else:
                    await message.reply(
                        response_text or "T nghẹn text r 💀",
                        mention_author=False,
                    )

                # Lưu vào chat_history
                config.chat_history[ctx_key].append(
                    {
                        "role": "user",
                        "parts": [clean_content],
                        "user_id": user_id,
                        "display_name": message.author.display_name or message.author.name,
                        "user_mention": f"<@{user_id}>",
                    }
                )
                config.chat_history[ctx_key].append(
                    {
                        "role": "model",
                        "parts": [response_text],
                    }
                )
                if len(config.chat_history[ctx_key]) > 15:
                    config.chat_history[ctx_key] = config.chat_history[ctx_key][-15:]
                
                # Increment daily usage sau khi gọi API thành công
                config.increment_daily_usage(user_id)
                    
        except Exception as error:
            error_str = str(error).lower()
            print(f"Lỗi API: {error}")
            
            # === BẮT LỖI RATE LIMIT (429) ===
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                embed = discord.Embed(
                    title="😴 API hết quota hôm nay rồi!",
                    description=(
                        f"**Gemini API** đã hết lượt sử dụng trong hôm nay! 💀\n\n"
                        f"• Bot sẽ không trả lời được cho tới khi **reset vào 0:00** 🕐\n"
                        f"• Các tính năng khác (lệnh, roleplay) vẫn hoạt động bình thường ✅\n\n"
                        f"**Giải pháp:** Chờ mai hoặc nhắn Owner nạp thêm API key! 😎"
                    ),
                    color=0xFF0040,
                )
                embed.set_footer(text="=)) hết xài r, để dành tiền nạp API đi bro")
                await message.reply(embed=embed, mention_author=False)
            elif message.author.id == config.OWNER_ID:
                await message.channel.send(f"Lỗi nè đại ca: `{error}` 💀")
                
        await bot.process_commands(message)

# --- HÀM PHỤ TRỢ (GIỮ NGUYÊN) ---
async def _build_invite_url(guild: discord.Guild):
    try:
        for channel in guild.channels:
            can_invite = (
                isinstance(channel, discord.TextChannel)
                and channel.permissions_for(guild.me).create_instant_invite
            )
            if can_invite:
                invite = await channel.create_invite(max_age=0, max_uses=0)
                return invite.url
    except Exception:
        return None
    return None