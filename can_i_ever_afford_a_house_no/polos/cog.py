from __future__ import annotations

import logging
import random
from collections import Counter
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from asgiref.sync import sync_to_async

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.polos")

BALLS_PER_POLO = 5
MAX_POLOS_PER_COMMAND = 100


def _get_enabled_balls():
    """Read enabled balls and their rarity values from the database."""
    from bd_models.models import Ball
    return list(
        Ball.objects.filter(enabled=True).only("id", "country", "rarity")
    )


def _get_or_create_player(discord_id: int):
    from bd_models.models import Player
    player, _ = Player.objects.get_or_create(discord_id=discord_id)
    return player


def _award_ball_instances(player_id: int, ball_ids: list[int]) -> None:
    """Create collection instances; duplicate balls are intentionally allowed."""
    from bd_models.models import BallInstance
    instances = [
        BallInstance(player_id=player_id, ball_id=ball_id)
        for ball_id in ball_ids
    ]
    BallInstance.objects.bulk_create(instances)


def _choose_ball_ids(balls, amount: int) -> list[int]:
    """Choose balls with rarity-based weights, tolerating unusual rarity data.

    Assumption: lower rarity values mean rarer balls in this BallsDex database,
    so weights are inverse to positive rarity values. If rarity in your fork uses
    the opposite convention, this weighting should be adjusted to match spawning.
    """
    candidates = []
    weights = []

    for ball in balls:
        try:
            rarity = float(ball.rarity)
        except (TypeError, ValueError):
            rarity = 1.0

        # Avoid division by zero and negative/invalid weights.
        weight = max(rarity, 0.000001)
        candidates.append(ball)
        weights.append(weight)

    if not candidates:
        return []

    return [ball.id for ball in random.choices(candidates, weights=weights, k=amount)]


class PolosCog(commands.Cog):
    """Admin command for granting Polos, each containing five balls."""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.polos_group = app_commands.Group(
            name="polos",
            description="polos",
        )
        self.polos_group.add_command(self.give)

    def cog_unload(self):
        self.bot.tree.remove_command("polos", type=discord.AppCommandType.chat_input)

    @app_commands.command(name="give", description="give someone verities")
    @app_commands.describe(
        user="who wants the verities",
        packs="1-100",
    )
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        packs: app_commands.Range[int, 1, MAX_POLOS_PER_COMMAND],
    ):
        # Restrict to Discord server administrators.
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "not an admin",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            balls = await sync_to_async(_get_enabled_balls, thread_sensitive=True)()
            if not balls:
                await interaction.followup.send(
                    "Add some balls first dude",
                    ephemeral=True,
                )
                return

            total_balls = packs * BALLS_PER_POLO
            selected_ids = _choose_ball_ids(balls, total_balls)

            player = await sync_to_async(
                _get_or_create_player, thread_sensitive=True
            )(user.id)
            await sync_to_async(
                _award_ball_instances, thread_sensitive=True
            )(player.id, selected_ids)

            ball_names = {ball.id: ball.country for ball in balls}
            counts = Counter(ball_names.get(ball_id, f"Ball #{ball_id}") for ball_id in selected_ids)
            summary = "\n".join(
                f"• **{name}** × {count}"
                for name, count in sorted(counts.items(), key=lambda item: item[0].casefold())
            )

            embed = discord.Embed(
                title="Verities Given!",
                description=(
                    f"Gave **{packs} Polo{'s' if packs != 1 else ''}** to {user.mention}.\n"
                    f"They received **{len(selected_ids)} balls/verities**."
                ),
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Verities awarded",
                value=summary[:1024] if summary else "??",
                inline=False,
            )
            if len(summary) > 1024:
                embed.set_footer(text="docker error")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            log.exception("jhgfrtyukjhgfgjkjnvfghjnbv %s", user.id)
            await interaction.followup.send(
                "Docker error occured, DM kaboomtsarbobm with the message.",
                ephemeral=True,
            )