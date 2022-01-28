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
from telegrambot import *
from discord.ext import commands



def saveConfig():

	global config, config_file

	logging.info("Saving configuration...")

	with open(config_file, "w") as f:
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
	bot.run(config["Discord"]["Token"])

	if bot:
		logging.info("Connected to discord successfullly.")

def loadDB() -> pymongo.database.Database:
	global config

	logging.info("Connecting to MongoDB...", )
	dbclient = pymongo.MongoClient("mongodb://%s:%s/" % (config["MongoDB"]["ip"], config["MongoDB"]["port"]))


	logging.info("Connected.")
	# Create the database / locate the database
	db = dbclient["discord_mule"]

	existing_col = db.list_collection_names()

	guild_info = db["guild_info"]	
	if "guild_info" not in existing_col:
		guild_info.insert_one(GUILD_TEMPLATE)

	tweet_info = db["tweet_info"]
	if "tweet_info" not in existing_col:
		tweet_info.insert_one(TWEET_TEMPLATE)

	twitter_info = db["twitter_info"]
	if "twitter_info" not in existing_col:
		twitter_info.insert_one(TWITTER_TEMPLATE)

	telegram_info = db["telegram_info"]
	if "telegram_info" not in existing_col:
		telegram_info.insert_one(TELEGRAM_TEMPLATE)

	return db


def main():
	global bot

	bot = commands.Bot(command_prefix="=", case_insensitive = True)

	@bot.event
	async def on_message(message: discord.Message) -> None:

		# if message.author != bot.user:
		# 	logging.info("Received from %s[%s]: %s" % (message.author, message.channel.id, message.content))

		await bot.process_commands(message)

	logging.basicConfig(level = logging.INFO) #, file="bot.log"

	config = loadConfig(file_name = "bot.conf")

	db = loadDB()
 

	@bot.event
	async def on_ready():
		logging.info("Logged in as %s [%s]" % (bot.user.id, bot.user))	


	if config["Discord"]["HandleCommands"] == "True":
		logging.info("Commands enabled.")
		bot.add_cog(General(bot, db))
		bot.add_cog(Role(bot, db))
		bot.add_cog(Voice(bot, config, db))
	else:
		logging.info("Commands disabled.")
  
	bot.add_cog(Twitter(bot, config, db))
	bot.add_cog(TelegramBot(bot, config, db))



	deployBot()



if __name__ == "__main__":
	main()




	

		