import discord
from discord import app_commands
from discord.ext import commands
import config
import datetime

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
                description="Bạn không có quyền **Administrator** để thực hiện lệnh này.",
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

    bot.tree.add_group(server_group)
