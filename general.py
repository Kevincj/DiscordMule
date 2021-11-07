#!/usr/bin/python3

import discord
import logging
import pymongo
import configparser
from kaomoji import kaomoji
from discord.ext import commands


class General(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.kao = kaomoji.Kaomoji()
		self.config = config
		self.db = db
	

	

	@commands.command(pass_context=True, help="show a kaomoji")
	async def hi(self, ctx: commands.Context):

		logging.info("Reacting with a random kaomoji...")

		await ctx.message.delete()
		await ctx.send(self.kao())


	@commands.Cog.listener()
	async def on_ready(self):
		
		logging.info("Logged in as %s [%s]" % (self.bot.user.id, self.bot.user))
