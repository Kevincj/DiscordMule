#!/usr/bin/python3

import json
import tweepy
import discord
import logging
import configparser
from kaomoji import kaomoji
from discord.ext import commands


# Initialize Discord bot
bot = commands.Bot(command_prefix = '-', case_insensitive = True)


def saveConfig() -> None:
	global config, config_file

	logging.info("Saving configuration...")

	with open('example.ini', 'w') as config_file:
		config.write(config_file)


def loadConfig(file_name:str = "bot.conf") -> None:

	global config, config_file

	config_file = file_name

	logging.info("Loading configuration...")

	config = configparser.ConfigParser()
	config.read('bot.conf')

	print(config.sections())


	
def loadKaomoji() -> None:

	global kao

	logging.info("Loading Kaomoji...")
	kao = kaomoji.Kaomoji()


def loadTwitter() -> None:
	global config, api

	api = None

	logging.info("Setting up Twitter access...")
	if 'AccessToken' in config['Twitter']:
		auth = tweepy.OAuthHandler(config['Twitter']['APIKey'], config['Twitter']['APISecret'])
		auth.set_access_token(config['Twitter']['AccessToken'], config['Twitter']['AccessSecret'])
		api = tweepy.API(auth)

	if not api:
		logging.info("Fetching access token and secret...")

		try:
			auth = tweepy.OAuthHandler(config['Twitter']['APIKey'], config['Twitter']['APISecret'])
			redirect_url = auth.get_authorization_url()
			logging.info("Link: %s" % redirect_url)
			verifier = input('PIN: ')
			config['Twitter']['AccessToken'], config['Twitter']['AccessSecret'] = \
									auth.get_access_token(verifier)

			logging.info("Received access token: %s" %  config['Twitter']['AccessToken'])
			logging.info("Received access token: %s" %  config['Twitter']['AccessSecret'])
			auth.set_access_token(config['Twitter']['AccessToken'], config['Twitter']['AccessSecret'])

			saveConfig(config_file)
			api = tweepy.API(auth)

		except tweepy.TweepyException as error:
			logging.info('Error!')

	if api:
		logging.info("Connected to Twitter successfullly.")
	else:
		logging.error("Failed to connect to Twitter.")


def initialize(config_file:str = "bot.conf") -> None:

	logging.basicConfig(level = logging.INFO) #, file='bot.log'

	loadConfig(file_name = config_file)
	loadKaomoji()
	loadTwitter()

def deployBot() -> None:
	global bot, config
	# Load Discord bot
	logging.info("Connecting to discord, token: %s" % config['Discord']['Token'])
	bot.run(config['Discord']['Token'])





""" 
	Events:

"""

@bot.event
async def on_ready() -> None:
	logging.info("Logged in as %s [%s]" % (bot.user.id, bot.user))


@bot.event
async def on_message(message: discord.Message) -> None:
	if message.author != bot.user:
		logging.info("Received from %s: %s" % (message.author, message.content))
	await bot.process_commands(message)




""" 
	Commands:
		-hi 	:Respond with a kaomoji

"""
@bot.command()
async def hi(ctx: commands.Context) -> None:
	'''Respond with a kaomoji'''
	global kao
	logging.info("Reacting with a random kaomoji...")

	await ctx.message.delete()
	await ctx.send(kao())






""" 
	Tasks:

"""








initialize()
deployBot()




	

		