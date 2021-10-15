#!/usr/bin/python3

import json
import tweepy
import discord
import logging
from kaomoji import kaomoji
from discord.ext import commands


# Initialize Discord bot
bot = commands.Bot(command_prefix = '-', case_insensitive = True)

def loadKaomoji():
	''' Load Kaomoji '''
	global kao

	logging.info("Setting up Kaomoji...")
	kao = kaomoji.Kaomoji()
	logging.info("Kaomoji ready: %s" % kao())

def saveConfig():
	global config
	logging.info("Saving configuration...")

	try:
		with open("bot.conf", "w") as f:
			json.dump(config, f)
		logging.info("Configuration saved successfullly.")
	except:
		logging.info("Error while saving configuration.")


def loadTwitter():
	global config, api

	api = None

	logging.info("Setting up Twitter access...")
	if 'twi_access_token' in config.keys():
		auth = tweepy.OAuthHandler(config['twi_api_key'], config['twi_api_secret'])
		auth.set_access_token(config['twi_access_token'], config['twi_access_secret'])
		api = tweepy.API(auth)

	else:
		logging.info("Access token invalid, refetching...")

		try:
			auth = tweepy.OAuthHandler(config['twi_api_key'], config['twi_api_secret'])
			redirect_url = auth.get_authorization_url()
			logging.info("Link: %s" % redirect_url)
			verifier = input('PIN: ')
			access_token, access_token_secret = auth.get_access_token(verifier)

			logging.info("Received access token: %s" %  access_token)
			logging.info("Received access token: %s" %  access_token_secret)
			auth.set_access_token(access_token, access_token_secret)
			config['twi_access_token'], config['twi_access_secret'] = access_token, access_token_secret

			saveConfig()
			api = tweepy.API(auth)

		except tweepy.TweepyException as error:
			logging.info('Error!')

	if api:
		logging.info("Connected to Twitter successfullly.")
	else:
		logging.error("Failed to connect to Twitter.")


@bot.event
async def on_ready():
	logging.info("Logged in as %s [%s]" % (bot.user.id, bot.user))

@bot.command()
async def hi(ctx):
	'''Respond with a kaomoji'''
	global kao
	logging.info("Reacting with a random kaomoji...")

	await ctx.message.delete()
	await ctx.send(kao())

@bot.event
async def on_message(message):

  await bot.process_commands(message)


def loadConfiguration():
	global config
	config = None

	logging.info("Load configuration...")
	try:
		with open("bot.conf", "r") as f:
			config = json.load(f)
	except:
		logging.error("Unable to load \'bot.conf\'.")
		return

	if config:
		logging.info("Loaded config file successfullly")
		return
	else:
		logging.error("\'bot.conf\' is empty.")
		return

def deployBot():
	global bot, config
	# Load Discord bot
	logging.info("Connecting to discord, token: %s" % config['discord_token'])
	bot.run(config['discord_token'])


logging.basicConfig(level=logging.INFO) #, file='bot.log'
loadConfiguration()

loadKaomoji()
loadTwitter()
deployBot()




	

		