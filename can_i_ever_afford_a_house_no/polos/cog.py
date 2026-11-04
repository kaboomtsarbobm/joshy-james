from __future__ import annotations

import logging
import random
from collections import Counter
from typing import TYPE_CHECKING

import discord
from asgiref.sync import sync_to_async
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.polos")

BALLS_PER_POLO = 5
MAX_POLOS_PER_COMMAND = 100
EMBED_FIELD_LIMIT = 1024
MIN_WEIGHT = 1e-6


def fetch_enabled_balls():
    from bd_models.models import Ball

    return list(Ball.objects.filter(enabled=True).only("id", "country", "rarity"))


def fetch_player(discord_id: int):
    from bd_models.models import Player

    player, _ = Player.objects.get_or_create(discord_id=discord_id)
    return player


def grant_balls(player_id: int, ball_ids: list[int]) -> None:
    from bd_models.models import BallInstance

    BallInstance.objects.bulk_create(
        BallInstance(player_id=player_id, ball_id=ball_id) for ball_id in ball_ids
    )


def rarity_weight(ball) -> float:
    try:
        return max(float(ball.rarity), MIN_WEIGHT)
    except (TypeError, ValueError):
        return 1.0


def roll_balls(balls, amount: int) -> list[int]:
    if not balls:
        return []

    weights = [rarity_weight(ball) for ball in balls]
    picked = random.choices(balls, weights=weights, k=amount)
    return [ball.id for ball in picked]


def format_summary(names: dict[int, str], ball_ids: list[int]) -> str:
    counts = Counter(names.get(i, f"Ball #{i}") for i in ball_ids)
    ordered = sorted(counts.items(), key=lambda pair: pair[0].casefold())
    return "\n".join(f"• **{name}** × {count}" for name, count in ordered)


def build_embed(user: discord.User, packs: int, total: int, summary: str) -> discord.Embed:
    plural = "s" if packs != 1 else ""
    embed = discord.Embed(
        title="Verities Given!",
        description=(
            f"Gave **{packs} Polo{plural}** to {user.mention}.\n"
            f"They received **{total} balls/verities**."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Verities awarded",
        value=summary[:EMBED_FIELD_LIMIT] or "??",
        inline=False,
    )
    if len(summary) > EMBED_FIELD_LIMIT:
        embed.set_footer(text="docker error")
    return embed


class PolosCog(commands.Cog):
    def __init__(self, bot: BallsDexBot):
        self.bot = bot
        self.polos_group = app_commands.Group(name="polos", description="polos")
        self.polos_group.add_command(self.give)

    def cog_unload(self):
        self.bot.tree.remove_command("polos", type=discord.AppCommandType.chat_input)

    @app_commands.command(name="give", description="give someone verities")
    @app_commands.describe(user="who wants the verities", packs="1-100")
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        packs: app_commands.Range[int, 1, MAX_POLOS_PER_COMMAND],
    ):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("not an admin", ephemeral=True)

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            balls = await sync_to_async(fetch_enabled_balls, thread_sensitive=True)()
            if not balls:
                return await interaction.followup.send("Add some balls first dude", ephemeral=True)

            ball_ids = roll_balls(balls, packs * BALLS_PER_POLO)

            player = await sync_to_async(fetch_player, thread_sensitive=True)(user.id)
            await sync_to_async(grant_balls, thread_sensitive=True)(player.id, ball_ids)

            names = {ball.id: ball.country for ball in balls}
            summary = format_summary(names, ball_ids)
            embed = build_embed(user, packs, len(ball_ids), summary)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            log.exception("jhgfrtyukjhgfgjkjnvfghjnbv %s", user.id)
            await interaction.followup.send(
                "Docker error occured, DM kaboomtsarbobm with the message.",
                ephemeral=True,
            )
