#!/usr/bin/python3

import discord
import logging
import pyttsx3
import youtube_dl
from discord.ext import commands
from discord import FFmpegPCMAudio


class Voice(commands.Cog):

	def __init__(self, bot: commands.Bot):

		self.bot = bot
		self.loadTTS()
		
	def loadTTS(self) -> None:

		logging.info("Loading TTS...")

		self.engine = pyttsx3.init()

		for voice in self.engine.getProperty('voices'):

			if "zhCN" in voice.id:

				logging.info("Setting voice as: %s" % voice.id)
				self.engine.setProperty("voice", voice.id)
				break

		self.engine.setProperty('rate', 145)
		
		self.engine.save_to_file("OK", "tmp.mp3")
		self.engine.runAndWait()



	@commands.command(pass_context=True)
	async def join(self, ctx: commands.Context) -> None:

		logging.info("Received -join request from %s" % ctx.author)

		if ctx.author.voice:
			channel = ctx.message.author.voice.channel
			await channel.connect()

		else:
			await ctx.say("Please join a voice channel before running this command.")


	@commands.command(pass_context=True)
	async def leave(self, ctx: commands.Context) -> None:

		logging.info("Received -leave request from %s" % ctx.author)

		if ctx.voice_client:
			await ctx.voice_client.disconnect()

		else:
			await ctx.send("I'm not in any voice channel of this server.")


	@commands.command(pass_context=True)
	async def say(self, ctx: commands.Context, *, arg) -> None:
		
		logging.info("Received -say request from %s: %s" % (ctx.author, arg))


		if ctx.author.voice.channel and ctx.voice_client and \
			ctx.author.voice.channel == ctx.voice_client.channel:

			self.engine.save_to_file(arg, "tmp.mp3")
			self.engine.runAndWait()
			source = FFmpegPCMAudio("tmp.mp3")
			player = ctx.voice_client.play(source)
			return

		else:

			await ctx.send("I'm not in your voice channel.")







	

		