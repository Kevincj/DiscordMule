#!/usr/bin/python3

import discord
import logging
from kaomoji import kaomoji
from discord.ext import commands


class General(commands.Cog):

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.kao = kaomoji.Kaomoji()


	@commands.command()
	async def hi(self, ctx: commands.Context) -> None:

		logging.info("Reacting with a random kaomoji...")

		await ctx.message.delete()
		await ctx.send(self.kao())








	

		