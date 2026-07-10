import time

import discord

import config


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


def register_events(bot):
    @bot.event
    async def on_ready():
        print(f"Bot đã đăng nhập với tên: {bot.user.name}")
        print(f"Default Model: {config.DEFAULT_MODEL_ID}")
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
        if message.author == bot.user or message.content.startswith("/"):
            await bot.process_commands(message)
            return

        if message.guild:
            guild_id = message.guild.id
            config.MSG_COUNTERS[guild_id] = config.MSG_COUNTERS.get(guild_id, 0) + 1

        is_dm = message.guild is None
        is_reply_to_bot = (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == bot.user
        )

        if not is_dm and bot.user not in message.mentions and not is_reply_to_bot:
            return

        if not config.IS_CHAT_ENABLED:
            return

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
                timestamp
                for timestamp in user_spam_data["last_msgs"]
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

        ctx_key = config.get_context_key(message)
        state = config.get_context_state(ctx_key)
        if state["active"]:
            system_instruction = (
                f"{state['config']['prompt']}\n\n{config.META_ROLEPLAY_PROMPT}"
            )
        else:
            system_instruction = config.DEFAULT_SYSTEM_PROMPT

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

        try:
            async with message.channel.typing():
                model = config.get_model(config.CURRENT_MODEL_ID)
                clean_content = config.strip_bot_mention(
                    message.content,
                    bot.user.id if bot.user else None,
                )

                if ctx_key not in config.chat_history:
                    config.chat_history[ctx_key] = []

                config.chat_history[ctx_key].append(
                    {
                        "role": "user",
                        "parts": [clean_content],
                        "user_id": user_id,
                        "display_name": message.author.display_name or message.author.name,
                        "user_mention": f"<@{user_id}>",
                    }
                )

                if len(config.chat_history[ctx_key]) > 15:
                    config.chat_history[ctx_key] = config.chat_history[ctx_key][-15:]

                parts = [system_instruction]
                for history_item in config.chat_history[ctx_key]:
                    if history_item["role"] == "user":
                        display_name = history_item.get("display_name", "User")
                        parts.append(
                            f"{display_name} (ID: {history_item.get('user_id')}): "
                            f"{history_item['parts'][0]}"
                        )
                    elif history_item["role"] == "model":
                        parts.append(f"Model: {history_item['parts'][0]}")

                if image_parts:
                    parts.extend(image_parts)

                response = await model.generate_content_async(parts)
                response_text = config.extract_response_text(response)
                if not response_text:
                    response_text = "T bị câm ngang API r, nói lại phát 💀"
                response_text = response_text[:2000].strip()

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

            config.chat_history[ctx_key].append(
                {
                    "role": "model",
                    "parts": [response_text],
                }
            )

            if len(config.chat_history[ctx_key]) > 15:
                config.chat_history[ctx_key] = config.chat_history[ctx_key][-15:]

        except Exception as error:
            print(f"Lỗi API: {error}")
            if message.author.id == config.OWNER_ID:
                await message.channel.send(f"Lỗi nè đại ca: `{error}` 💀")

        await bot.process_commands(message)
