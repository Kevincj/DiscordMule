#!/usr/bin/python3

import os
import json
import discord
import logging
import pymongo
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

def loadDB() -> pymongo.database.Database:

	logging.info("Connecting to MongoDB...")
	dbclient = pymongo.MongoClient("mongodb://localhost:27017/")

	# Create the database / locate the database
	db = dbclient["discord_mule"]

	existing_col = db.list_collection_names()

	guild_info = db["guild_info"]	
	if "guild_info" not in existing_col:
		guild_info.insert_one(GUILD_TEMPLATE)

	tweet_info = db["tweet_info"]
	if "tweet_info" not in existing_col:
		tweet_info.insert_one(TWEET_TEMPLATE)

	user_info = db["user_info"]
	if "user_info" not in existing_col:
		user_info.insert_one(USER_TEMPLATE)

	return db


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

	db = loadDB()



	bot.add_cog(General(bot, db))
	bot.add_cog(Role(bot, db))
	bot.add_cog(Voice(bot, db))
	bot.add_cog(Twitter(bot, config, db))



	deployBot()



if __name__ == '__main__':
	main()




	

		