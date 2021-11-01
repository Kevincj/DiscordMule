#!/usr/bin/python3

import os
import json
import discord
import logging
import configparser
from role import *
from voice import *
from twitter import *
from general import *
from discord.ext import commands


def saveConfig():

	global config, config_file

	logging.info("Saving configuration...")

	with open(config_file, 'w') as f:
		config.write(f)



def loadConfig(file_name:str = "bot.conf"):

	global config, config_file

	config_file = file_name

	logging.info("Loading configuration...")

	config = configparser.ConfigParser()
	config.read(file_name)
	return config




def deployBot() -> None:

	global bot, config

	# Load Discord bot
	logging.info("Connecting to discord...")
	bot.run(config['Discord']['Token'])

	if bot:
		logging.info("Connected to discord successfullly.")




def main():
	global bot

	bot = commands.Bot(command_prefix='=', case_insensitive = True)

	@bot.event
	async def on_message(message: discord.Message) -> None:

		if message.author != bot.user:
			logging.info("Received from %s: %s" % (message.author, message.content))

		await bot.process_commands(message)

	logging.basicConfig(level = logging.INFO) #, file='bot.log'

	config = loadConfig(file_name = "bot.conf")




	bot.add_cog(General(bot, config))
	bot.add_cog(Role(bot, config))
	bot.add_cog(Voice(bot, config))
	bot.add_cog(Twitter(bot, config))



	deployBot()



if __name__ == '__main__':
	main()




	

		