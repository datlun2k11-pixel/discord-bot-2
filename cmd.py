# cmd.py
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

    # --- MAIN SERVER SETTINGS GROUP ---
    @bot.tree.command(name="server_setting", description="Hệ thống quản lý server tối thượng")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        action="Hành động cần thực hiện",
        target="Thành viên cần tác động (cho kick/ban/timeout)",
        role="Vai trò cần thao tác (cho role commands)",
        channel="Kênh cần thao tác (cho channel/slowmode commands)",
        name="Tên (cho role/channel commands)",
        color="Mã màu hex (cho role commands)",
        hoist="Hiển thị vai trò riêng biệt (cho role commands)",
        new_name="Tên mới (cho role edit)",
        new_color="Màu mới (cho role edit)",
        type="Loại kênh: text hoặc voice (cho new_channel)",
        category="Danh mục chứa kênh (cho new_channel)",
        reason="Lý do (cho kick/ban/timeout)",
        duration_minutes="Thời gian timeout (phút)",
        seconds="Thời gian slowmode (giây, 0 để tắt)",
        delete_message_days="Số ngày tin nhắn bị xóa khi ban"
    )
    async def server_setting(
        interaction: discord.Interaction,
        action: str,
        target: discord.Member = None,
        role: discord.Role = None,
        channel: discord.TextChannel = None,
        name: str = None,
        color: str = "#FFFFFF",
        hoist: bool = False,
        new_name: str = None,
        new_color: str = None,
        type: str = "text",
        category: discord.CategoryChannel = None,
        reason: str = "Không có lý do",
        duration_minutes: int = 5,
        seconds: int = 0,
        delete_message_days: int = 1
    ):
        """Lệnh quản lý server đa năng"""
        
        # Danh sách actions có sẵn
        valid_actions = [
            "add_role", "edit_role", "delete_role",
            "new_channel",
            "kick", "ban", "timeout",
            "slowmode"
        ]
        
        if action not in valid_actions:
            embed = discord.Embed(
                title="❌ Action không hợp lệ",
                description=f"Actions có sẵn: {', '.join(valid_actions)}",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # --- XỬ LÝ TỪNG ACTION ---
        
        # 1. ROLE MANAGEMENT
        if action == "add_role":
            if not name:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `name` để tạo vai trò mới.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            try:
                color_obj = discord.Color.from_str(color)
                new_role = await interaction.guild.create_role(name=name, color=color_obj, hoist=hoist)
                embed = discord.Embed(
                    title="✅ Vai trò đã được tạo",
                    description=f"Vai **{name}** đã được thêm vào server.",
                    color=SUCCESS_COLOR
                )
                embed.add_field(name="Màu sắc", value=color, inline=True)
                embed.add_field(name="Hiển thị riêng", value=str(hoist), inline=True)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi tạo vai trò: {str(e)}", ephemeral=True)
        
        elif action == "edit_role":
            if not role:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `role` để chỉnh sửa.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            try:
                updates = {}
                if new_name:
                    updates['name'] = new_name
                if new_color:
                    updates['color'] = discord.Color.from_str(new_color)
                await role.edit(**updates)
                embed = discord.Embed(
                    title="✏️ Vai trò đã được cập nhật",
                    description=f"Vai **{role.name}** đã được thay đổi.",
                    color=SUCCESS_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi chỉnh sửa: {str(e)}", ephemeral=True)
        
        elif action == "delete_role":
            if not role:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `role` để xóa.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Bot không đủ quyền hạn để xóa vai này (vai cao hơn hoặc bằng bot).", ephemeral=True)
                return
            try:
                role_name = role.name
                await role.delete()
                embed = discord.Embed(
                    title="🗑️ Vai trò đã bị xóa",
                    description=f"Vai **{role_name}** đã biến mất khỏi vũ trụ.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi xóa vai trò: {str(e)}", ephemeral=True)
        
        # 2. CHANNEL MANAGEMENT
        elif action == "new_channel":
            if not name:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `name` để tạo kênh mới.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            try:
                if type.lower() == "text":
                    await interaction.guild.create_text_channel(name=name, category=category)
                else:
                    await interaction.guild.create_voice_channel(name=name, category=category)
                embed = discord.Embed(
                    title="📢 Kênh mới đã sẵn sàng",
                    description=f"Kênh **{name}** đã được tạo thành công.",
                    color=SUCCESS_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi tạo kênh: {str(e)}", ephemeral=True)
        
        # 3. MODERATION
        elif action == "kick":
            if not target:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `target` để kick.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if target.top_role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Bot không đủ quyền để đuổi người này.", ephemeral=True)
                return
            try:
                await target.kick(reason=reason)
                embed = discord.Embed(
                    title="👢 Thành viên đã bị đá",
                    description=f"**{target.name}** đã bị đuổi vì: {reason}\nNgười thực hiện: {interaction.user.name}",
                    color=ERROR_COLOR
                )
                embed.set_footer(text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi kick: {str(e)}", ephemeral=True)
        
        elif action == "ban":
            if not target:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `target` để ban.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if target.top_role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Bot không đủ quyền để ban người này.", ephemeral=True)
                return
            try:
                await target.ban(reason=reason, delete_message_days=delete_message_days)
                embed = discord.Embed(
                    title="🔨 Thành viên đã bị Ban",
                    description=f"**{target.name}** đã bị cấm vĩnh viễn.\nLý do: {reason}\nXóa tin nhắn: {delete_message_days} ngày gần nhất.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi ban: {str(e)}", ephemeral=True)
        
        elif action == "timeout":
            if not target:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Cần cung cấp `target` để timeout.",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if target.top_role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Bot không đủ quyền để timeout người này.", ephemeral=True)
                return
            try:
                duration = datetime.timedelta(minutes=duration_minutes)
                await target.timeout(duration, reason=reason)
                embed = discord.Embed(
                    title="🤐 Thành viên đã bị bịt miệng",
                    description=f"**{target.name}** bị câm trong {duration_minutes} phút.\nLý do: {reason}",
                    color=0xFFA500
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi timeout: {str(e)}", ephemeral=True)
        
        # 4. UTILITY
        elif action == "slowmode":
            target_channel = channel or interaction.channel
            try:
                await target_channel.edit(slowmode_delay=seconds)
                if seconds > 0:
                    msg = f"Slowmode đã được đặt thành {seconds}s."
                else:
                    msg = "Slowmode đã bị tắt."
                embed = discord.Embed(
                    title="⏱️ Slowmode Updated",
                    description=msg,
                    color=BRAND_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Lỗi slowmode: {str(e)}", ephemeral=True)

    # --- LỆNH PING ĐƠN GIẢN ---
    @bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Độ trễ: {latency}ms")
        