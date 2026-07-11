import discord
from discord import app_commands

import config


def register_commands(bot):
    @bot.tree.command(name="getlink", description="Lấy link vào server - Chỉ Owner")
    @app_commands.describe(server_id="ID của server cần lấy link")
    async def getlink_command(interaction: discord.Interaction, server_id: str):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("M k phải owner, cút! 🔪", ephemeral=True)
            return

        try:
            guild_id = int(server_id)
            guild = bot.get_guild(guild_id)

            if not guild:
                await interaction.response.send_message(
                    f"Không tìm thấy server với ID: `{guild_id}` 💀",
                    ephemeral=True,
                )
                return

            invite_url = None
            try:
                for channel in guild.channels:
                    can_invite = (
                        isinstance(channel, discord.TextChannel)
                        and channel.permissions_for(guild.me).create_instant_invite
                    )
                    if can_invite:
                        invite = await channel.create_invite(max_age=0, max_uses=0)
                        invite_url = invite.url
                        break
            except Exception:
                pass

            if not invite_url:
                await interaction.response.send_message(
                    f"Không thể tạo link cho server `{guild.name}` 💀",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"🔗 Link vào server: {guild.name}",
                color=0x00F0FF,
                description=(
                    f"**Server ID:** {guild_id}\n"
                    f"**Số thành viên:** {guild.member_count}\n\n"
                    f"**Link:** {invite_url}"
                ),
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else "")

            await interaction.user.send(embed=embed)
            await interaction.response.send_message(
                "✅ Đã gửi link vào DM của bạn 🥀",
                ephemeral=True,
            )

        except ValueError:
            await interaction.response.send_message(
                "Server ID phải là số nha! 🤡",
                ephemeral=True,
            )
        except Exception as error:
            await interaction.response.send_message(
                f"Lỗi: `{error}` 💀",
                ephemeral=True,
            )

    @bot.tree.command(
        name="server_list",
        description="Xem toàn bộ thông tin các server bot đang ở - Chỉ Owner",
    )
    async def server_list_command(interaction: discord.Interaction):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("M k phải owner, cút! 🔪", ephemeral=True)
            return

        guilds = bot.guilds
        if not guilds:
            await interaction.response.send_message(
                "Bot chưa join server nào hết á đại ca! 🥀",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📊 Danh sách các server ({len(guilds)} server)",
            color=0x00F0FF,
        )
        sorted_guilds = sorted(guilds, key=lambda guild: guild.member_count, reverse=True)
        total_members = sum(guild.member_count for guild in guilds)
        embed.set_footer(text=f"Tổng cộng: {total_members} thành viên")

        for guild in sorted_guilds[:25]:
            field_value = (
                f"**ID:** {guild.id}\n"
                f"**Thành viên:** {guild.member_count}\n"
                f"**Owner:** <@{guild.owner_id}>"
            )
            embed.add_field(name=guild.name, value=field_value, inline=False)

        if len(sorted_guilds) > 25:
            embed.description = (
                f"*Đang hiển thị 25 server đầu tiên, tổng cộng {len(sorted_guilds)} server*"
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="roleplay", description="Quản lý chế độ nhập vai (Hỗ trợ cả DM)")
@app_commands.choices(
    action=[
        app_commands.Choice(name="🎭 Chọn vai có sẵn", value="select"),
        app_commands.Choice(name="✏️ Tạo vai mới", value="custom"),
        app_commands.Choice(name="🗑️ Xoá vai đã tạo", value="delete"),
        app_commands.Choice(name="📋 Xem vai hiện tại", value="status"),
        app_commands.Choice(name="❌ Tắt nhập vai", value="off"),
    ]
)
async def roleplay_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
):
    ctx_key = config.get_context_key(interaction)

    if interaction.guild_id:
        has_mod_rights = (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.guild_permissions.moderate_members
        )
        if interaction.user.id != config.OWNER_ID and not has_mod_rights:
            await interaction.response.send_message(
                "M k có quyền chỉnh setting, cút! 🔪",
                ephemeral=True,
            )
            return

    if action.value == "off":
        config.set_context_state(ctx_key, False, None)
        # ✅ PUBLIC - Gửi ra channel cho mọi người thấy
        await interaction.channel.send(
            f"❌ **{interaction.user.display_name}** đã tắt nhập vai. Về lại GenZ gốc 😎"
        )
        await interaction.response.send_message(
            "Đã tắt nhập vai.",  # Reply riêng cho người dùng
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
