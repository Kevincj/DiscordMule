#!/usr/bin/python3

import json
import discord
import logging
from kaomoji import kaomoji
from discord.ext import commands


# Initialize Discord bot

class DiscordCog(commands.Cog):

	def __init__(self, bot: commands.Bot):
		self.bot = bot

		# Load kaomoji
		logging.info("Setting up Kaomoji...")
		self.kao = kaomoji.Kaomoji()
		logging.info("Kaomoji ready: %s" % self.kao())

	


	@commands.Cog.listener()
	async def on_ready(self):
		logging.info("Logged in as %s [%s]" % (self.bot.user.id, self.bot.user))

	@commands.command()
	async def hi(self, ctx: commands.Context):
		'''Respond with a kaomoji'''
		await ctx.message.delete()
		await ctx.send(self.kao())


def initialize():
	global kao






def loadConfiguration():

	logging.info("Load configuration...")
	try:
		with open("bot.conf", "r") as f:
			conf = json.load(f)
	except:
		logging.error("Unable to load \'bot.conf\'.")
		return None

	if conf:
		logging.info("Loaded config file successfullly")
		return conf
	else:
		logging.error("\'bot.conf\' is empty.")
		return None

def deployBot():
	global bot, config
	# Load Discord bot
	logging.info("Connecting to discord, token: %s" % config['discord_token'])
	bot.run(config['discord_token'])


logging.basicConfig(level=logging.INFO) #, file='bot.log'
bot = commands.Bot(command_prefix='-')
bot.add_cog(DiscordCog(bot))
config = loadConfiguration()
deployBot()




	

		