#!/usr/bin/python3

import os
import json
import tweepy
import discord
import logging
import pyttsx3
import youtube_dl
import configparser
from general import *
from discord.ext import commands
from discord import FFmpegPCMAudio


def saveConfig() -> None:

	global config, config_file

	logging.info("Saving configuration...")

	with open(config_file, 'w') as f:
		config.write(f)


def loadConfig(file_name:str = "bot.conf") -> None:

	global config, config_file

	config_file = file_name

	logging.info("Loading configuration...")

	config = configparser.ConfigParser()
	config.read('bot.conf')

	return config





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

	return api


def loadTTS() -> None:
	global engine
	engine = pyttsx3.init()
	engine.setProperty('rate', 145)
	engine.save_to_file("OK", "tmp.mp3")
	engine.runAndWait()






def deployBot() -> None:

	global bot, config

	# Load Discord bot
	logging.info("Connecting to discord, token: %s" % config['Discord']['Token'])
	bot.run(config['Discord']['Token'])





# """ 
# 	Events:

# """

# @bot.event
# async def on_ready() -> None:

# 	logging.info("Logged in as %s [%s]" % (bot.user.id, bot.user))


# @bot.event
# async def on_message(message: discord.Message) -> None:

# 	if message.author != bot.user:
# 		logging.info("Received from %s: %s" % (message.author, message.content))

# 	await bot.process_commands(message)


# @bot.event
# async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):

# 	pass
# 	# bot.voice_client


# """ 
# 	Commands:
# 		-hi 		:Respond with a kaomoji
# 		-join		:Join your voice channel
# 		-leave		:Leave the current channel
# 		-say XXX	:Speak XXX in your voice channel
# """





# @bot.command(pass_context=True)
# async def join(ctx: commands.Context) -> None:

# 	if ctx.author.voice:
# 		channel = ctx.message.author.voice.channel
# 		await channel.connect()
# 	else:
# 		await ctx.say("Please join a voice channel before running this command.")


# @bot.command(pass_context=True)
# async def leave(ctx: commands.Context) -> None:

# 	if ctx.voice_client:

# 		await ctx.voice_client.disconnect()
# 	else:
# 		await ctx.send("I'm not in any voice channel of this server.")


# @bot.command(pass_context=True)
# async def say(ctx: commands.Context, *, arg) -> None:

# 	global engine

# 	if ctx.author.voice.channel and ctx.voice_client and \
# 		ctx.author.voice.channel == ctx.voice_client.channel:

# 		engine.save_to_file(" ".join(arg), "tmp.mp3")
# 		engine.runAndWait()
# 		source = FFmpegPCMAudio("tmp.mp3")
# 		player = ctx.voice_client.play(source)
# 		return

# 	else:

# 		await ctx.send("I'm not in your voice channel.")



# """ 
# 	Tasks:

# """




def main():
	global bot

	bot = commands.Bot(command_prefix='-', case_insensitive = True)

	logging.basicConfig(level = logging.INFO) #, file='bot.log'

	config = loadConfig(file_name = "bot.conf")

	# loadTwitter()
	# loadTTS()

	@bot.event
	async def on_ready():
		print("Logged in.")

	bot.add_cog(General(bot))


	
	deployBot()



if __name__ == '__main__':
	main()




	

		