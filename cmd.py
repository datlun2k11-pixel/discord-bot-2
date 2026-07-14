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

    # --- SERVER MANAGEMENT GROUP ---
    server_group = app_commands.Group(name="server_setting", description="Hệ thống quản lý server tối thượng")

    # --- CONFIGURATION SUBCOMMANDS ---
    @server_group.command(name="add_role", description="Tạo vai mới với màu sắc tùy chỉnh")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_role(interaction: discord.Interaction, name: str, color: str = "#FFFFFF", hoist: bool = False):
        try:
            color_obj = discord.Color.from_str(color)
            role = await interaction.guild.create_role(name=name, color=color_obj, hoist=hoist)
            role_desc = "Vai **" + name + "** đã được thêm vào server."
            embed = discord.Embed(title="✅ Vai đã được tạo", description=role_desc, color=SUCCESS_COLOR)
            embed.add_field(name="Màu sắc", value=color, inline=True)
            embed.add_field(name="Hiển thị riêng", value=str(hoist), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi tạo vai: " + str(e), ephemeral=True)

    @server_group.command(name="edit_role", description="Chỉnh sửa tên hoặc màu của vai")
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_role(interaction: discord.Interaction, role: discord.Role, new_name: str = None, new_color: str = None):
        try:
            updates = {}
            if new_name:
                updates['name'] = new_name
            if new_color:
                updates['color'] = discord.Color.from_str(new_color)
            await role.edit(**updates)
            edit_desc = "Vai **" + role.name + "** đã được thay đổi."
            embed = discord.Embed(title="✏️ Vai đã được cập nhật", description=edit_desc, color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi chỉnh sửa: " + str(e), ephemeral=True)

    @server_group.command(name="delete_role", description="Xóa vĩnh viễn một vai khỏi server")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_role(interaction: discord.Interaction, role: discord.Role):
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền hạn để xóa vai này (vai cao hơn hoặc bằng bot).", ephemeral=True)
            return
        try:
            await role.delete()
            delete_desc = "Vai **" + role.name + "** đã biến mất khỏi vũ trụ."
            embed = discord.Embed(title="🗑️ Vai đã bị xóa", description=delete_desc, color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi xóa vai: " + str(e), ephemeral=True)

    @server_group.command(name="new_channel", description="Tạo kênh văn bản hoặc thoại mới")
    @app_commands.checks.has_permissions(administrator=True)
    async def new_channel(interaction: discord.Interaction, name: str, category: discord.CategoryChannel = None, type: str = "text"):
        try:
            if type == "text":
                await interaction.guild.create_text_channel(name=name, category=category)
            else:
                await interaction.guild.create_voice_channel(name=name, category=category)
            ch_desc = "Kênh **" + name + "** đã được tạo thành công."
            embed = discord.Embed(title="📢 Kênh mới đã sẵn sàng", description=ch_desc, color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi tạo kênh: " + str(e), ephemeral=True)

    # --- MODERATION SUBCOMMANDS ---
    @server_group.command(name="kick", description="Đuổi cổ thành viên ra khỏi server")
    @app_commands.checks.has_permissions(administrator=True)
    async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Vi phạm nội quy"):
        if member.top_role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền để đuổi người này.", ephemeral=True)
            return
        try:
            await member.kick(reason=reason)
            kick_desc = "**{0}** đã bị đuổi vì: {1}".format(member.name, reason)
            kick_desc += "\nNgười thực hiện: " + interaction.user.name
            embed = discord.Embed(title="👢 Member đã bị đá", description=kick_desc, color=ERROR_COLOR)
            embed.set_footer(text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi kick: " + str(e), ephemeral=True)

    @server_group.command(name="ban", description="Cấm cửa vĩnh viễn và xóa tin nhắn")
    @app_commands.checks.has_permissions(administrator=True)
    async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Nguy hiểm", delete_message_days: int = 1):
        if member.top_role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền để ban người này.", ephemeral=True)
            return
        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
            ban_desc = "**{0}** đã bị cấm vĩnh viễn.".format(member.name)
            ban_desc += "\nLý do: " + reason
            ban_desc += "\nXóa tin nhắn: " + str(delete_message_days) + " ngày gần nhất."
            embed = discord.Embed(title="🔨 Member đã bị Ban", description=ban_desc, color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi ban: " + str(e), ephemeral=True)

    @server_group.command(name="timeout", description="Bịt miệng tạm thời (Timeout)")
    @app_commands.checks.has_permissions(administrator=True)
    async def timeout(interaction: discord.Interaction, member: discord.Member, duration_minutes: int, reason: str = "Nói nhiều quá"):
        if member.top_role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền để timeout người này.", ephemeral=True)
            return
        try:
            duration = datetime.timedelta(minutes=duration_minutes)
            await member.timeout(duration, reason=reason)
            timeout_desc = "**{0}** bị câm trong {1} phút.".format(member.name, str(duration_minutes))
            timeout_desc += "\nLý do: " + reason
            embed = discord.Embed(title="🤐 Member đã bị Bịt miệng", description=timeout_desc, color=0xFFA500)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi timeout: " + str(e), ephemeral=True)

    # --- UTILITY SUBCOMMANDS ---
    @server_group.command(name="slowmode", description="Cài đặt tốc độ chat chậm")
    @app_commands.checks.has_permissions(administrator=True)
    async def slowmode(interaction: discord.Interaction, channel: discord.TextChannel = None, seconds: int = 0):
        target_channel = channel or interaction.channel
        try:
            await target_channel.edit(slowmode_delay=seconds)
            if seconds > 0:
                msg = "Slowmode đã được đặt thành " + str(seconds) + "s."
            else:
                msg = "Slowmode đã bị tắt."
            embed = discord.Embed(title="⏱️ Slowmode Updated", description=msg, color=BRAND_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Lỗi slowmode: " + str(e), ephemeral=True)

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
    
    # FIX LỖI CHÍNH: Đăng ký group vào tree
    bot.tree.add_command(server_group)
    
    # Thêm lệnh /ping đơn giản để test
    @bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Độ trễ: {latency}ms")