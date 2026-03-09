from __future__ import annotations

import logging

import discord
from discord.ext import commands

from absence_bot.commands import AbsenceCommandRegistrar


class AbsenceBot(commands.Bot):
    def __init__(
        self,
        *,
        command_registrar: AbsenceCommandRegistrar,
        report_service,
        scheduler,
        runtime_state,
    ) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True

        super().__init__(command_prefix="!", intents=intents)
        self._command_registrar = command_registrar
        self._report_service = report_service
        self._scheduler = scheduler
        self._runtime_state = runtime_state
        self._logger = logging.getLogger("absence_bot.discord")

    async def setup_hook(self) -> None:
        self._command_registrar.register(self)
        await self.tree.sync()
        await self._scheduler.start()

    async def on_ready(self) -> None:
        self._runtime_state.gateway_ready = True
        self._logger.info("discord gateway ready", extra={"user": str(self.user)})

    async def close(self) -> None:
        self._runtime_state.gateway_ready = False
        await self._scheduler.stop()
        await super().close()

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild_id = str(member.guild.id)
        user_id = str(member.id)
        before_channel_id = str(before.channel.id) if before.channel else None
        after_channel_id = str(after.channel.id) if after.channel else None

        try:
            await self._report_service.handle_voice_state_update(
                guild_id=guild_id,
                user_id=user_id,
                before_channel_id=before_channel_id,
                after_channel_id=after_channel_id,
                display_name=member.display_name,
            )
        except Exception:
            self._logger.exception(
                "voice_state handler failed",
                extra={"guild_id": guild_id, "user_id": user_id},
            )
