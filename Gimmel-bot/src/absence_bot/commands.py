from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands

from absence_bot.models import GuildSettings, MentionMode, PostMode, TrackMode, TrackedUser
from absence_bot.templates import chunk_lines
from absence_bot.time_utils import format_local_date, now_utc, utc_iso, validate_daily_time, validate_timezone


class AbsenceCommandRegistrar:
    def __init__(
        self,
        storage,
        report_service,
        scheduler,
        default_timezone: str,
        default_daily_time: str,
        default_template: str,
        retention_days: int,
    ) -> None:
        self._storage = storage
        self._report_service = report_service
        self._scheduler = scheduler
        self._default_timezone = default_timezone
        self._default_daily_time = default_daily_time
        self._default_template = default_template
        self._retention_days = retention_days

    def register(self, bot: discord.Client) -> None:
        group = app_commands.Group(name="absence", description="Управление отчётами отсутствия")

        @group.command(name="help", description="Показать гайд по командам и примерам")
        async def help_command(interaction: discord.Interaction) -> None:
            await self._send_ephemeral_help(interaction)

        @group.command(name="add", description="Добавить пользователя в отслеживание")
        @app_commands.describe(user="Пользователь", display_name_override="Имя в отчёте")
        async def add(
            interaction: discord.Interaction,
            user: discord.Member,
            display_name_override: Optional[str] = None,
        ) -> None:
            if not await self._ensure_admin(interaction):
                return
            guild_id = str(interaction.guild_id)
            await self._ensure_settings(guild_id)

            tracked_user = TrackedUser(
                guild_id=guild_id,
                user_id=str(user.id),
                display_name=display_name_override or user.display_name,
                enabled=True,
                added_by_user_id=str(interaction.user.id),
                added_at_utc=utc_iso(),
            )
            await self._storage.tracked_users.add(tracked_user)
            await interaction.response.send_message(
                f"Пользователь {user.mention} добавлен в отслеживание.",
                ephemeral=True,
            )

        @group.command(name="remove", description="Удалить пользователя из отслеживания")
        async def remove(interaction: discord.Interaction, user: discord.Member) -> None:
            if not await self._ensure_admin(interaction):
                return
            guild_id = str(interaction.guild_id)
            await self._storage.tracked_users.remove(guild_id, str(user.id))
            await interaction.response.send_message(
                f"Пользователь {user.mention} удалён из отслеживания.",
                ephemeral=True,
            )

        @group.command(name="list", description="Список отслеживаемых пользователей")
        async def list_users(interaction: discord.Interaction, page: Optional[int] = 1) -> None:
            if not await self._ensure_admin(interaction):
                return
            guild_id = str(interaction.guild_id)
            rows = await self._report_service.build_rows(guild_id)
            if not rows:
                await interaction.response.send_message("Список отслеживания пуст.", ephemeral=True)
                return

            page_size = 10
            page = max(page or 1, 1)
            start = (page - 1) * page_size
            end = start + page_size
            selected = rows[start:end]
            if not selected:
                await interaction.response.send_message("Нет записей на этой странице.", ephemeral=True)
                return

            lines = []
            for row in selected:
                if row.days_absent is None:
                    lines.append(f"• {row.display_name} (`{row.user_id}`): нет данных")
                else:
                    lines.append(
                        f"• {row.display_name} (`{row.user_id}`): {row.days_absent} дн. (последний визит {row.last_seen_date})"
                    )

            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        @group.command(name="enable", description="Включить ежедневные отчёты")
        async def enable(interaction: discord.Interaction) -> None:
            if not await self._ensure_admin(interaction):
                return
            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.enabled = True
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await self._scheduler.reload_jobs()
            await interaction.response.send_message("Ежедневные отчёты включены.", ephemeral=True)

        @group.command(name="disable", description="Выключить ежедневные отчёты")
        async def disable(interaction: discord.Interaction) -> None:
            if not await self._ensure_admin(interaction):
                return
            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.enabled = False
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await self._scheduler.reload_jobs()
            await interaction.response.send_message("Ежедневные отчёты выключены.", ephemeral=True)

        @group.command(name="configure-channel", description="Установить канал для отчётов")
        async def configure_channel(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
        ) -> None:
            if not await self._ensure_admin(interaction):
                return
            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.report_channel_id = str(channel.id)
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await self._scheduler.reload_jobs()
            await interaction.response.send_message(
                f"Канал отчётов установлен: {channel.mention}",
                ephemeral=True,
            )

        @group.command(name="set-timezone", description="Установить таймзону")
        async def set_timezone(interaction: discord.Interaction, tz: str) -> None:
            if not await self._ensure_admin(interaction):
                return
            try:
                validate_timezone(tz)
            except Exception:
                await interaction.response.send_message("Некорректная timezone.", ephemeral=True)
                return

            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.timezone = tz
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await self._scheduler.reload_jobs()
            await interaction.response.send_message(f"Timezone обновлена: `{tz}`", ephemeral=True)

        @group.command(name="set-template", description="Установить шаблон сообщения")
        async def set_template(interaction: discord.Interaction, template: str) -> None:
            if not await self._ensure_admin(interaction):
                return
            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.template_text = template.strip()
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await interaction.response.send_message("Шаблон обновлён.", ephemeral=True)

        @group.command(name="set-post-mode", description="Режим публикации")
        @app_commands.choices(
            mode=[
                app_commands.Choice(name="single", value="single"),
                app_commands.Choice(name="per_user", value="per_user"),
            ]
        )
        async def set_post_mode(
            interaction: discord.Interaction,
            mode: app_commands.Choice[str],
        ) -> None:
            if not await self._ensure_admin(interaction):
                return
            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.post_mode = PostMode(mode.value)
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await interaction.response.send_message(f"Режим публикации: `{mode.value}`", ephemeral=True)

        @group.command(name="set-mention-mode", description="Режим упоминаний")
        @app_commands.choices(
            mode=[
                app_commands.Choice(name="no_ping", value="no_ping"),
                app_commands.Choice(name="ping", value="ping"),
            ]
        )
        async def set_mention_mode(
            interaction: discord.Interaction,
            mode: app_commands.Choice[str],
        ) -> None:
            if not await self._ensure_admin(interaction):
                return
            settings = await self._ensure_settings(str(interaction.guild_id))
            settings.mention_mode = MentionMode(mode.value)
            settings.updated_at_utc = utc_iso()
            await self._storage.guild_settings.upsert(settings)
            await interaction.response.send_message(f"Режим упоминаний: `{mode.value}`", ephemeral=True)

        @group.command(name="run", description="Принудительно запустить отчёт")
        async def run(interaction: discord.Interaction) -> None:
            if not await self._ensure_admin(interaction):
                return
            guild_id = str(interaction.guild_id)
            sent = await self._scheduler.run_now(guild_id)
            await interaction.response.send_message(
                f"Ручной запуск завершён. Отправлено сообщений: {sent}.",
                ephemeral=True,
            )

        @group.command(name="optout", description="Управление opt-out")
        @app_commands.choices(
            mode=[
                app_commands.Choice(name="enable", value="enable"),
                app_commands.Choice(name="disable", value="disable"),
            ]
        )
        async def optout(
            interaction: discord.Interaction,
            mode: app_commands.Choice[str],
            reason: Optional[str] = None,
        ) -> None:
            if interaction.guild_id is None:
                await interaction.response.send_message("Команда доступна только в сервере.", ephemeral=True)
                return

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            tracked = await self._storage.tracked_users.get(guild_id, user_id)
            if tracked is None:
                await self._storage.tracked_users.add(
                    TrackedUser(
                        guild_id=guild_id,
                        user_id=user_id,
                        display_name=getattr(interaction.user, "display_name", interaction.user.name),
                        enabled=False,
                        added_by_user_id=user_id,
                        added_at_utc=utc_iso(),
                    )
                )

            enabled = mode.value == "enable"
            await self._storage.optout.set(guild_id, user_id, enabled, reason)
            status_text = "включён" if enabled else "выключен"
            await interaction.response.send_message(f"Opt-out {status_text}.", ephemeral=True)

        @group.command(name="status", description="Показать статус отслеживания")
        async def status(interaction: discord.Interaction) -> None:
            if interaction.guild_id is None:
                await interaction.response.send_message("Команда доступна только в сервере.", ephemeral=True)
                return

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            tracked = await self._storage.tracked_users.get(guild_id, user_id)
            opt = await self._storage.optout.get(guild_id, user_id)
            settings = await self._ensure_settings(guild_id)
            activity = await self._storage.activity.get(guild_id, user_id)

            tracked_status = "да" if tracked and tracked.enabled else "нет"
            opted_out = "да" if opt and opt.opted_out else "нет"
            last_seen = (
                format_local_date(activity.last_seen_at_utc, settings.timezone)
                if activity and activity.last_seen_at_utc
                else "нет данных"
            )
            message = (
                f"Отслеживается: {tracked_status}\n"
                f"Opt-out: {opted_out}\n"
                f"Последний визит: {last_seen}\n"
                f"Retention: {self._retention_days} дней"
            )
            await interaction.response.send_message(message, ephemeral=True)

        @group.command(name="privacy", description="Показать информацию о приватности")
        async def privacy(interaction: discord.Interaction) -> None:
            text = (
                "Бот хранит: user_id, display_name, время последнего визита в voice/stage и channel_id.\n"
                f"Рекомендуемый срок хранения: {self._retention_days} дней.\n"
                "Вы можете отключить обработку через /absence optout."
            )
            await interaction.response.send_message(text, ephemeral=True)

        bot.tree.add_command(group)

    async def _ensure_admin(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or interaction.guild_id is None:
            await interaction.response.send_message("Команда доступна только в сервере.", ephemeral=True)
            return False

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Не удалось проверить права.", ephemeral=True)
            return False

        if not member.guild_permissions.manage_guild:
            await interaction.response.send_message("Требуется право Manage Guild.", ephemeral=True)
            return False

        return True

    async def _ensure_settings(self, guild_id: str) -> GuildSettings:
        settings = await self._storage.guild_settings.get(guild_id)
        if settings is not None:
            return settings

        settings = GuildSettings(
            guild_id=guild_id,
            enabled=True,
            report_channel_id=None,
            timezone=self._default_timezone,
            daily_time=self._default_daily_time,
            template_text=self._default_template,
            post_mode=PostMode.SINGLE,
            mention_mode=MentionMode.NO_PING,
            track_mode=TrackMode.VOICE_ONLY,
            updated_at_utc=utc_iso(),
        )
        await self._storage.guild_settings.upsert(settings)
        await self._scheduler.reload_jobs()
        return settings

    async def _send_ephemeral_help(self, interaction: discord.Interaction) -> None:
        lines = self._help_guide_text().splitlines()
        chunks = chunk_lines(lines, max_len=1900)
        if not chunks:
            chunks = ["Гайд недоступен."]

        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)

    def _help_guide_text(self) -> str:
        return (
            "**/absence help — гайд**\n"
            "Подсчёт дней: только voice/stage. Точка отсчёта — выход из голосового.\n"
            "Дни = полные 24 часа после выхода (до 24ч будет 0).\n\n"
            "**Админ-команды**\n"
            "/absence add user:@Valeria display_name_override:Валерий\n"
            "/absence remove user:@Valeria\n"
            "/absence list page:1\n"
            "/absence enable\n"
            "/absence disable\n"
            "/absence configure-channel channel:#daily-absence\n"
            "/absence set-timezone tz:Europe/Moscow\n"
            "/absence set-template template:Прошло **{days} {days_word}** с момента как {user_mention} покинул нас.\n"
            "/absence set-post-mode mode:single\n"
            "/absence set-mention-mode mode:no_ping\n"
            "/absence run\n\n"
            "**Пользовательские команды**\n"
            "/absence optout mode:enable reason:Не хочу участвовать\n"
            "/absence status\n"
            "/absence privacy\n\n"
            "**Плейсхолдеры шаблона**\n"
            "{days}, {days_word}, {display_name}, {user_id}, {user_mention}, {last_seen_date}, {last_seen_channel_id}\n"
            "Чтобы упомянуть пользователя в шаблоне используйте {user_mention}.\n"
            "Если mode:no_ping, упоминание без уведомления; если mode:ping, с уведомлением.\n"
            "Текстовые сообщения не влияют на счётчик дней."
        )
