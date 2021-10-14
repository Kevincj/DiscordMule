#!/usr/bin/python3

import json
import discord
import logging
from kaomoji import kaomoji
from discord.ext import commands


# Initialize bot
logging.info("Initialize discord bot...")
bot = commands.Bot(command_prefix = '-', case_insensitive = True)

def initialize():
	global config, kao, bot

	# Load kaomoji
	logging.info("Setting up Kaomoji...")
	kao = kaomoji.Kaomoji()
	logging.info("Kaomoji ready: %s" % kao())


	logging.info("Connecting to discord, token: %s" % config['discord_token'])
	bot.run(config['discord_token'])


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


@bot.event
async def on_ready():
	global bot
	logging.info("Logged in as %s [%s]" % (bot.user.id, bot.user))

  








if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO) #, file='bot.log'

	config = loadConfiguration()

	if config: 
		initialize()

		