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
            # Fallback for other errors
            embed = discord.Embed(
                title="💀 Lỗi hệ thống",
                description=f"Đã xảy ra lỗi: `{str(error)}`",
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
            # Convert hex color
            color_obj = discord.Color.from_str(color)
            role = await interaction.guild.create_role(name=name, color=color_obj, hoist=hoist)
            
            embed = discord.Embed(title="✅ Vai đã được tạo", description=f"Vai **{name}** đã được thêm vào server.", color=SUCCESS_COLOR)
            embed.add_field(name="Màu sắc", value=color, inline=True)
            embed.add_field(name="Hiển thị riêng", value=str(hoist), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi tạo vai: {e}", ephemeral=True)

    @server_group.command(name="edit_role", description="Chỉnh sửa tên hoặc màu của vai")
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_role(interaction: discord.Interaction, role: discord.Role, new_name: str = None, new_color: str = None):
        try:
            updates = {}
            if new_name: updates['name'] = new_name
            if new_color: updates['color'] = discord.Color.from_str(new_color)
            
            await role.edit(**updates)
            embed = discord.Embed(title="✏️ Vai đã được cập nhật", description=f"Vai **{role.name}** đã được thay đổi.", color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi chỉnh sửa: {e}", ephemeral=True)

    @server_group.command(name="delete_role", description="Xóa vĩnh viễn một vai khỏi server")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_role(interaction: discord.Interaction, role: discord.Role):
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền hạn để xóa vai này (vai cao hơn hoặc bằng bot).", ephemeral=True)
            return
        try:
            await role.delete()
            embed = discord.Embed(title="🗑️ Vai đã bị xóa", description=f"Vai **{role.name}** đã biến mất khỏi vũ trụ.", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi xóa vai: {e}", ephemeral=True)

    @server_group.command(name="new_channel", description="Tạo kênh văn bản hoặc thoại mới")
    @app_commands.checks.has_permissions(administrator=True)
    async def new_channel(interaction: discord.Interaction, name: str, category: discord.CategoryChannel = None, type: str = "text"):
        try:
            channel_type = discord.ChannelType.text if type == "text" else discord.ChannelType.voice
            await interaction.guild.create_text_channel(name=name, category=category) if type == "text" else await interaction.guild.create_voice_channel(name=name, category=category)
            embed = discord.Embed(title="📢 Kênh mới đã sẵn sàng", description=f"Kênh **{name}** đã được tạo thành công.", color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi tạo kênh: {e}", ephemeral=True)

    # --- MODERATION SUBCOMMANDS ---
    @server_group.command(name="kick", description="Đuổi cổ thành viên ra khỏi server")
    @app_commands.checks.has_permissions(administrator=True)
    async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Vi phạm nội quy"):
        if member.top_role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền để đuổi người này.", ephemeral=True)
            return
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(title="👢 Member đã bị đá", description=f"**{member.name}** đã bị đuổi vì: {reason}
Người thực hiện: {interaction.user.name}", color=ERROR_COLOR)
            embed.set_footer(text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi kick: {e}", ephemeral=True)

    @server_group.command(name="ban", description="Cấm cửa vĩnh viễn và xóa tin nhắn")
    @app_commands.checks.has_permissions(administrator=True)
    async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Nguy hiểm", delete_message_days: int = 1):
        if member.top_role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền để ban người này.", ephemeral=True)
            return
        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
            embed = discord.Embed(title="🔨 Member đã bị Ban", description=f"**{member.name}** đã bị cấm vĩnh viễn.
Lý do: {reason}
Xóa tin nhắn: {delete_message_days} ngày gần nhất.", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi ban: {e}", ephemeral=True)

    @server_group.command(name="timeout", description="Bịt miệng tạm thời (Timeout)")
    @app_commands.checks.has_permissions(administrator=True)
    async def timeout(interaction: discord.Interaction, member: discord.Member, duration_minutes: int, reason: str = "Nói nhiều quá"):
        if member.top_role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("Bot không đủ quyền để timeout người này.", ephemeral=True)
            return
        try:
            duration = datetime.timedelta(minutes=duration_minutes)
            await member.timeout(duration, reason=reason)
            embed = discord.Embed(title="🤐 Member đã bị Bịt miệng", description=f"**{member.name}** bị câm trong {duration_minutes} phút.
Lý do: {reason}", color=0xFFA500)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi timeout: {e}", ephemeral=True)

    # --- UTILITY SUBCOMMANDS ---
    @server_group.command(name="slowmode", description="Cài đặt tốc độ chat chậm")
    @app_commands.checks.has_permissions(administrator=True)
    async def slowmode(interaction: discord.Interaction, channel: discord.TextChannel = None, seconds: int = 0):
        target_channel = channel or interaction.channel
        try:
            await target_channel.edit(slowmode_delay=seconds)
            msg = f"Slowmode đã được đặt thành {seconds}s." if seconds > 0 else "Slowmode đã bị tắt."
            embed = discord.Embed(title="⏱️ Slowmode Updated", description=msg, color=BRAND_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi slowmode: {e}", ephemeral=True)

    @server_group.command(name="clear_messages", description="Xóa hàng loạt tin nhắn")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_messages(interaction: discord.Interaction, amount: int = 10):
        if amount > 100: amount = 100
        try:
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(title="🧹 Dọn dẹp hoàn tất", description=f"Đã xóa {len(deleted)} tin nhắn.", color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Lỗi xóa tin nhắn: {e}", ephemeral=True)

    @server_group.command(name="info", description="Xem thông tin chi tiết về server")
    @app_commands.checks.has_permissions(administrator=True)
    async def server_info(interaction: discord.Interaction):
        guild = interaction.guild
        humans = sum(not m.bot for m in guild.members)
        bots = sum(m.bot for m in guild.members)
        
        embed = discord.Embed(title=f"📊 Thông tin Server: {guild.name}", color=BRAND_COLOR)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="👑 Owner", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="🆔 Server ID", value=str(guild.id), inline=True)
        embed.add_field(name="📅 Thành lập", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="👥 Thành viên", value=f"Total: {guild.member_count}\nHumans: {humans}\nBots: {bots}", inline=True)
        embed.add_field(name="🛡️ Cấp độ xác minh", value=str(guild.verification_level), inline=True)
        embed.add_field(name="📢 Kênh", value=f"Text: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}", inline=True)
        
        await interaction.response.send_message(embed=embed)

    # Register the group to the bot's tree
    bot.tree.add_command(server_group)
            ephemeral=True,
        )
        return

    if action.value == "status":
        state = config.get_context_state(ctx_key)
        if state["active"]:
            embed = discord.Embed(
                title="🎭 Đang nhập vai",
                description=f"**Vai:** {state['config']['name']}",
                color=0x00FF00,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Bot đang ở chế độ GenZ gốc.",
                ephemeral=True,
            )
        return

    if action.value == "select":
        all_roles = {**config.SAMPLE_ROLES, **config.USER_ROLES}
        if not all_roles:
            await interaction.response.send_message(
                "Chưa có vai nào cả! Tạo vai mới đi bro 💀",
                ephemeral=True,
            )
            return

        options = [
            discord.SelectOption(label=role["name"], value=role_key)
            for role_key, role in all_roles.items()
        ]
        select = discord.ui.Select(placeholder="Chọn 1 vai...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            chosen = all_roles[select.values[0]]
            config.set_context_state(ctx_key, True, chosen)
            
            # ✅ PUBLIC - Gửi ra channel cho mọi người thấy
            await select_interaction.channel.send(
                f"🎭 **{select_interaction.user.display_name}** vừa bật vai **{chosen['name']}**! Chuẩn bị tinh thần đi các ní 🤡"
            )
            await select_interaction.response.send_message(
                f"Đã bật vai **{chosen['name']}** 🔥",
                ephemeral=True,  # Vẫn giữ ephemeral cho người dùng
            )

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Chọn vai:", view=view, ephemeral=True)
        return

    if action.value == "custom":
        class CustomModal(discord.ui.Modal, title="Tạo vai mới"):
            name = discord.ui.TextInput(label="Tên vai")
            prompt = discord.ui.TextInput(
                label="Prompt",
                style=discord.TextStyle.paragraph,
                max_length=2000,
            )

            async def on_submit(self, modal_inter: discord.Interaction):
                role_key = self.name.value.lower().strip().replace(" ", "_")
                role_config = {"name": self.name.value, "prompt": self.prompt.value}
                
                config.USER_ROLES[role_key] = role_config
                config.set_context_state(ctx_key, True, role_config)
                
                # ✅ PUBLIC - Gửi ra channel cho mọi người thấy
                await modal_inter.channel.send(
                    f"✨ **{modal_inter.user.display_name}** vừa tạo và bật role **{self.name.value}**! Chắc sẽ vui đây 🤣"
                )
                await modal_inter.response.send_message(
                    f"Đã tạo và bật vai **{self.name.value}** ✅\n"
                    f"Vai này đã được lưu vào 'Role có sẵn' để dùng sau nha! 🔥",
                    ephemeral=True,
                )

        await interaction.response.send_modal(CustomModal())
        return

    if action.value == "delete":
        if not config.USER_ROLES:
            await interaction.response.send_message(
                "Chưa có vai nào do bạn tạo cả! 🤡\n"
                "(Chỉ có thể xoá vai do user tạo, ko xoá đc role hệ thống)",
                ephemeral=True,
            )
            return

        options = [
            discord.SelectOption(label=role["name"], value=role_key)
            for role_key, role in config.USER_ROLES.items()
        ]
        select = discord.ui.Select(placeholder="Chọn vai để xoá...", options=options)

        async def delete_callback(delete_interaction: discord.Interaction):
            role_key = select.values[0]
            deleted_role = config.USER_ROLES.pop(role_key, None)
            if deleted_role:
                # ✅ PUBLIC - Gửi ra channel cho mọi người thấy
                await delete_interaction.channel.send(
                    f"🗑️ **{delete_interaction.user.display_name}** đã xoá role **{deleted_role['name']}**"
                )
                await delete_interaction.response.send_message(
                    f"Đã xoá vai **{deleted_role['name']}** 🗑️",
                    ephemeral=True,
                )
            else:
                await delete_interaction.response.send_message(
                    "Xoá thất bại, thử lại đi 💀",
                    ephemeral=True,
                )

        select.callback = delete_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(
            "Chọn vai muốn xoá:\n*(Chỉ hiện vai do bạn tạo)*",
            view=view,
            ephemeral=True,
        )
        return

    @bot.tree.command(name="setting", description="Chỉnh config bot - Chỉ Owner")
    @app_commands.describe(
        max_tokens="Số token tối đa AI trả về",
        temperature="Độ sáng tạo 0.0-1.0",
        chat_enabled="Bật/tắt chat",
    )
    async def setting_command(
        interaction: discord.Interaction,
        max_tokens: int = None,
        temperature: float = None,
        chat_enabled: bool = None,
    ):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("M k phải owner, tuổi? 🔪", ephemeral=True)
            return

        messages = []
        if max_tokens is not None:
            if max_tokens <= 0:
                await interaction.response.send_message(
                    "`max_tokens` phải lớn hơn 0 🤡",
                    ephemeral=True,
                )
                return
            config.CURRENT_MAX_TOKENS = max_tokens
            messages.append(f"Max tokens: `{max_tokens}`")

        if temperature is not None:
            if not 0.0 <= temperature <= 1.0:
                await interaction.response.send_message(
                    "`temperature` phải nằm trong khoảng `0.0 -> 1.0` 💀",
                    ephemeral=True,
                )
                return
            config.CURRENT_TEMPERATURE = temperature
            messages.append(f"Temperature: `{temperature}`")

        if chat_enabled is not None:
            config.IS_CHAT_ENABLED = chat_enabled
            messages.append(f"Chat: `{'Bật' if chat_enabled else 'Tắt'}`")

        if not messages:
            ctx_key = config.get_context_key(interaction)
            state = config.get_context_state(ctx_key)
            await interaction.response.send_message(
                f"""
**Config hiện tại:**
- Model: `{config.CURRENT_MODEL_ID}`
- Max tokens: `{config.CURRENT_MAX_TOKENS}`
- Temperature: `{config.CURRENT_TEMPERATURE}`
- Chat enabled: `{config.IS_CHAT_ENABLED}`
- Roleplay: `{state['config']['name'] if state['active'] else 'Tắt'}`
""",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Đã update: " + ", ".join(messages),
            ephemeral=True,
        )

    @bot.tree.command(name="usage", description="Xem thống kê tin nhắn các server - Chỉ Owner")
    async def usage_command(interaction: discord.Interaction):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("Tuổi j xem usage của t? 🔪", ephemeral=True)
            return

        if not config.MSG_COUNTERS:
            await interaction.response.send_message(
                "Chưa có server nào nhắn j hết á đại ca! 🥀",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title="📊 Thống kê usage tin nhắn", color=0x00F0FF)
        total_all = 0

        for guild_id, count in config.MSG_COUNTERS.items():
            guild = bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"Server ẩn ({guild_id})"
            embed.add_field(name=guild_name, value=f"`{count}` tin nhắn", inline=False)
            total_all += count

        embed.set_footer(text=f"Tổng cộng toàn bộ server: {total_all} tin nhắn")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="model", description="Đổi model Gemini - Chỉ Owner")
    @app_commands.describe(model_name="Tên model: gemini-3.1-flash-lite, gemini-3.5-pro,...")
    async def model_command(interaction: discord.Interaction, model_name: str):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message(
                "Chỉ owner mới đổi đc model nha bro 💀",
                ephemeral=True,
            )
            return

        try:
            test_model = config.get_model(model_name)
            await test_model.generate_content_async("ping")
            config.CURRENT_MODEL_ID = model_name
            await interaction.response.send_message(
                f"Đã đổi sang model `{model_name}` ✅",
                ephemeral=True,
            )
        except Exception as error:
            await interaction.response.send_message(
                f"Model lỗi r: `{error}`",
                ephemeral=True,
            )

    @bot.tree.command(name="reset", description="Xóa lịch sử chat (Hỗ trợ cả DM)")
    async def reset_command(interaction: discord.Interaction):
        ctx_key = config.get_context_key(interaction)
        if ctx_key in config.chat_history:
            del config.chat_history[ctx_key]
        await interaction.response.send_message(
            "Đã reset memory cho khu vực này 🧹",
            ephemeral=True,
        )
