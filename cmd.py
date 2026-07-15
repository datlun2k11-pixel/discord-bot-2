import discord
from discord import app_commands
from discord.ext import commands
import config
import datetime
from typing import Optional

# Branding màu sắc cho Embed
BRAND_COLOR = 0x00F0FF
ERROR_COLOR = 0xFF0040
SUCCESS_COLOR = 0x00FF88
LEVEL_COLOR = 0x9B59B6  # Màu tím cho level

def register_commands(bot):
    # --- GLOBAL ERROR HANDLER FOR PERMISSIONS ---
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Bạn không có quyền Administrator để thực hiện lệnh này.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            err_desc = "Đã xảy ra lỗi: `" + str(error) + "`"
            embed = discord.Embed(
                title="💀 Lỗi hệ thống",
                description=err_desc,
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- ROLEPLAY COMMAND (DỄ DÙNG CHO MỌI NGƯỜI) ---
    @bot.tree.command(name="roleplay", description="Bật/Tắt chế độ nhập vai với các tính cách có sẵn")
    async def roleplay(interaction: discord.Interaction, action: str = "list", character: str = None):
        """
        action: 'list' (xem danh sách), 'start' (bắt đầu), 'stop' (dừng)
        character: tên nhân vật (chỉ cần khi action là 'start')
        """
        ctx_key = config.get_context_key(interaction)
        
        # 1. Xem danh sách nhân vật
        if action == "list":
            roles_list = "\n".join([f"- **{k}**: {v['name']}" for k, v in config.SAMPLE_ROLES.items()])
            embed = discord.Embed(
                title="🎭 Danh sách tính cách có sẵn",
                description=f"Dùng lệnh `/roleplay start <tên>` để bắt đầu.\n\n{roles_list}",
                color=BRAND_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Dừng nhập vai
        if action == "stop":
            config.set_context_state(ctx_key, False, None)
            embed = discord.Embed(
                title="🛑 Đã tắt chế độ nhập vai",
                description="Bot đã trở về trạng thái GenZ bình thường.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 3. Bắt đầu nhập vai
        if action == "start":
            if not character or character.lower() not in config.SAMPLE_ROLES:
                available = ", ".join(config.SAMPLE_ROLES.keys())
                await interaction.response.send_message(
                    f"❌ Sai tên nhân vật rồi bro! Chọn 1 trong mấy cái này: `{available}`",
                    ephemeral=True
                )
                return
            
            selected_role = config.SAMPLE_ROLES[character.lower()]
            config.set_context_state(ctx_key, True, selected_role)
            
            embed = discord.Embed(
                title=f"🎭 Đang nhập vai: {selected_role['name']}",
                description="Từ giờ t sẽ nói chuyện đúng tính cách này. Thử tag t xem nào!",
                color=SUCCESS_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=False) # Public để mọi người cùng thấy và chơi chung
            return

        # Fallback nếu nhập sai action
        await interaction.response.send_message("❌ Lệnh không hợp lệ. Dùng `/roleplay list` để xem hướng dẫn.", ephemeral=True)

    # --- RANK COMMAND ---
    @bot.tree.command(name="rank", description="Xem level và XP của bạn (hoặc người khác)")
    async def rank(interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Xem level/XP của bản thân hoặc người khác"""
        target = user or interaction.user
        
        # Nếu là DM thì không có guild
        if not interaction.guild:
            await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong server!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        data = config.get_xp_data(guild_id, target.id)
        xp = data["xp"]
        level = data["level"]
        
        # Tính XP cần cho level hiện tại và level tiếp theo
        xp_for_current_level = config.get_level_xp_required(level)
        xp_for_next_level = config.get_level_xp_required(level + 1)
        xp_current_level_start = config.get_level_xp_required(level)
        xp_progress = xp - xp_current_level_start
        xp_needed = xp_for_next_level - xp_current_level_start
        
        # Progress bar
        if xp_needed > 0:
            progress_pct = min(xp_progress / xp_needed, 1.0)
            bar_length = 10
            filled = int(progress_pct * bar_length)
            bar = "🟪" * filled + "⬜" * (bar_length - filled)
        else:
            bar = "🟪" * 10
        
        # Tạo embed
        embed = discord.Embed(
            title=f"📊 Level & XP",
            color=LEVEL_COLOR,
            description=f"**{target.display_name}**"
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🎯 Level", value=str(level), inline=True)
        embed.add_field(name="✨ XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="📈 Tiến độ", value=f"{bar} `{xp_progress}/{xp_needed}`", inline=False)
        
        # Tính rank trong server
        all_users = config.get_xp_for_guild(guild_id)
        rank_position = 1
        for i, (uid, uxp, ulevel) in enumerate(all_users):
            if int(uid) == target.id:
                rank_position = i + 1
                break
        embed.set_footer(text=f"Rank #{rank_position} trong server • Chat nhiều để lên level!")
        
        await interaction.response.send_message(embed=embed)

    # --- LEADERBOARD COMMAND ---
    @bot.tree.command(name="leaderboard", description="Xem bảng xếp hạng level trong server")
    async def leaderboard(interaction: discord.Interaction):
        """Xem top 10 người có level/XP cao nhất server"""
        if not interaction.guild:
            await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong server!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        all_users = config.get_xp_for_guild(guild_id)
        
        if not all_users:
            embed = discord.Embed(
                title="🏆 Leaderboard",
                description="Chưa có ai có XP trong server này! Hãy chat với bot để kiếm XP nhé! 🎯",
                color=LEVEL_COLOR
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Lấy top 10
        top_users = all_users[:10]
        
        # Medal emojis
        medals = ["🥇", "🥈", "🥉"]
        
        embed = discord.Embed(
            title=f"🏆 Bảng xếp hạng • {interaction.guild.name}",
            description="Top 10 người chăm chỉ nhất server!",
            color=LEVEL_COLOR
        )
        
        lines = []
        for i, (user_id_str, xp, level) in enumerate(top_users):
            rank_icon = medals[i] if i < 3 else f"**#{i+1}**"
            try:
                member = interaction.guild.get_member(int(user_id_str))
                name = member.display_name if member else f"<@{user_id_str}>"
            except Exception:
                name = f"<@{user_id_str}>"
            
            # Format XP
            xp_str = f"{xp:,}"
            lines.append(f"{rank_icon} **Level {level}** • {name} `({xp_str} XP)`")
        
        embed.description = "\n".join(lines)
        
        # Tính total users
        embed.set_footer(text=f"Tổng số: {len(all_users)} người tham gia")
        
        await interaction.response.send_message(embed=embed)

    # --- SETTING COMMAND (ADMIN/OWNER) ---
    @bot.tree.command(name="setting", description="[Admin] Tùy chỉnh cấu hình bot cho server")
    @app_commands.checks.has_permissions(administrator=True)
    async def setting(
        interaction: discord.Interaction,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        chat_enabled: Optional[bool] = None,
    ):
        """
        Tùy chỉnh cấu hình bot cho server hiện tại.
        - max_tokens: Số token tối đa (128-8192, để trống giữ nguyên)
        - temperature: Độ sáng tạo (0.0-2.0, để trống giữ nguyên)
        - chat_enabled: Bật/tắt chat AI (True/False, để trống giữ nguyên)
        """
        guild_id = str(interaction.guild.id)
        
        # Lấy settings hiện tại (hoặc tạo mới với giá trị mặc định)
        current = config.GUILD_SETTINGS.get(guild_id, {})
        
        changed = []
        
        if max_tokens is not None:
            if max_tokens < 128 or max_tokens > 8192:
                await interaction.response.send_message(
                    "❌ `max_tokens` phải từ 128 đến 8192!",
                    ephemeral=True
                )
                return
            current["max_tokens"] = max_tokens
            changed.append(f"max_tokens: {max_tokens}")
        
        if temperature is not None:
            if temperature < 0.0 or temperature > 2.0:
                await interaction.response.send_message(
                    "❌ `temperature` phải từ 0.0 đến 2.0!",
                    ephemeral=True
                )
                return
            current["temperature"] = temperature
            changed.append(f"temperature: {temperature}")
        
        if chat_enabled is not None:
            current["chat_enabled"] = chat_enabled
            changed.append(f"chat_enabled: {chat_enabled}")
        
        # Nếu không có gì thay đổi -> hiển thị settings hiện tại
        if not changed:
            max_t = current.get("max_tokens", config.DEFAULT_MAX_TOKENS)
            temp = current.get("temperature", config.DEFAULT_TEMPERATURE)
            enabled = current.get("chat_enabled", True)
            
            embed = discord.Embed(
                title="⚙️ Cấu hình server hiện tại",
                color=BRAND_COLOR,
                description=f"**Server:** {interaction.guild.name}"
            )
            embed.add_field(name="Max Tokens", value=str(max_t), inline=True)
            embed.add_field(name="Temperature", value=str(temp), inline=True)
            embed.add_field(name="Chat Enabled", value="✅ Bật" if enabled else "❌ Tắt", inline=True)
            embed.set_footer(text="Dùng /setting <option> <value> để thay đổi")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Lưu settings
        config.GUILD_SETTINGS[guild_id] = current
        config.save_all_data()
        
        embed = discord.Embed(
            title="✅ Đã cập nhật cấu hình",
            color=SUCCESS_COLOR,
            description="\n".join([f"• Đã đặt **{c}**" for c in changed])
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    # Thêm lệnh /ping đơn giản để test
    @bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Độ trễ: {latency}ms")