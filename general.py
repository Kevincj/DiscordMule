#!/usr/bin/python3

import discord
import logging
import pymongo
import configparser
from kaomoji import kaomoji
from discord.ext import commands


class General(commands.Cog):

	def __init__(self, bot: commands.Bot, db: pymongo.database.Database):
		self.bot = bot
		self.kao = kaomoji.Kaomoji()
		self.db = db
	

	

	@commands.command(pass_context=True, help="show a kaomoji")
	async def hi(self, ctx: commands.Context):

		logging.info("Reacting with a random kaomoji...")

		await ctx.message.delete()
		await ctx.send(self.kao())



	@commands.Cog.listener()
	async def on_ready(self):
		
		logging.info("Logged in as %s [%s]" % (self.bot.user.id, self.bot.user))



	@commands.command(pass_context=True, help="delete # messages")
	async def rm(self, ctx: commands.Context = None, *, message :str):
		try:
			count = int(message) +1
		except:
			await ctx.message.delete()
			return
	  
		try:
			
			messages = await ctx.channel.history(limit=count).flatten()
			for msg in messages:
				await msg.delete()
			logging.info("Successfully deleted %d messages." % len(messages))
		except:
			logging.info("Error while deleting...")



	@commands.command(pass_context=True, help="delete nth message")
	async def rmat(self, ctx: commands.Context = None, *, message :str):
		try:
			count = int(message)
		except:
			await ctx.message.delete()
			return

		try:
			messages = await ctx.channel.history(limit=count).flatten()
			msg = messages[-1]
			logging.info("Deleting:", type(msg), msg.content)
			await msg.delete()
			logging.info("Successfully deleted 1 message.")
		except:
			logging.info("Error while deleting...")