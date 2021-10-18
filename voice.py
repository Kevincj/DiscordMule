#!/usr/bin/python3

import discord
import logging
import pyttsx3
import youtube_dl
import discord.utils as utils
from discord.ext import commands
from youtube_dl import YoutubeDL
from discord import FFmpegPCMAudio
from collections import defaultdict

class Voice(commands.Cog):

	def __init__(self, bot: commands.Bot):

		self.bot = bot

		self.playing = False
		self.ydl = None
		self.play_states = defaultdict(lambda: {'playing': False, 'queue': [], 'current': None})
		self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

		self.loadTTS()


		self.loadYDL()


		
	def loadTTS(self) -> None:

		logging.info("Loading TTS...")

		self.engine = pyttsx3.init()

		for voice in self.engine.getProperty('voices'):

			if "zhCN" in voice.id:

				logging.info("Setting voice as: %s" % voice.id)
				self.engine.setProperty("voice", voice.id)
				break

		self.engine.setProperty('rate', 145)
		
		# self.engine.save_to_file("OK", "tmp.mp3")
		# self.engine.runAndWait()

	def loadYDL(self) -> None:

		logging.info("Loading youtube_dl...")

		YDL_OPTIONS = {
						'format': 'bestaudio', 
						# 'noplaylist':'True'
						}
		self.ydl = YoutubeDL(YDL_OPTIONS)




	@commands.command(pass_context=True)
	async def join(self, ctx: commands.Context):

		logging.info("Received -join request from %s" % ctx.author)

		if not ctx.author.voice:
			return await ctx.say("Please join a voice channel before running this command.")

		voice_client = utils.get(ctx.bot.voice_clients, guild = ctx.guild)

		if voice_client and voice_client.is_connected():

			if ctx.author.voice.channel == voice_client.channel: return

			logging.info("Disconnecting current voice channel...")
			await ctx.voice_client.disconnect()

		logging.info("Joining voice channel...")
		await ctx.author.voice.channel.connect()
			


	@commands.command(pass_context=True)
	async def leave(self, ctx: commands.Context):

		logging.info("Received -leave request from %s" % ctx.author)

		voice_client = utils.get(ctx.bot.voice_clients, guild = ctx.guild)

		if voice_client:
			await voice_client.disconnect()

		else:
			await ctx.send("I'm not in any voice channel of this server.")


	@commands.command(pass_context=True)
	async def say(self, ctx: commands.Context, *, arg: str):
		
		logging.info("Received -say request from %s: %s" % (ctx.author, arg))

		if not ctx.author.voice:
			return await ctx.send("Please join a voice channel before running this command.")

		voice_client = utils.get(ctx.bot.voice_clients, guild = ctx.guild)

		if not self.inSameVoiceChannel(ctx.author.voice, ctx.voice_client):
			return await ctx.send("I'm not in your voice channel.")


		self.engine.save_to_file(arg, "tmp.mp3")
		self.engine.runAndWait()
		return voice_client.play(FFmpegPCMAudio("tmp.mp3"))


	@commands.command(pass_context=True)
	async def p(self, ctx: commands.Context, *, kw: str):

		if not ctx.author.voice:
			return await ctx.say("Please join a voice channel before running this command.")

		if not self.inSameVoiceChannel(ctx.author.voice, ctx.voice_client):
			return await ctx.send("I'm not in your voice channel.")

		song_info = self.getSongInfo(kw)

		if not song_info:
			return await ctx.send("Unable to find the song, please try another keyword.")

		print("Song found: %s", song_info)
		self.play_states[ctx.guild.id]['queue'].append(song_info)
		await ctx.send("Added %s to queue" % song_info['title'])

		if not self.play_states[ctx.guild.id]['playing']:
			await self.play(ctx)


	@commands.command(pass_context=True)
	async def pause(self, ctx):
		voice_client = utils.get(self.bot.voice_clients, guild = ctx.guild)
		if voice_client.is_playing():
			voice_client.pause()
		else:
			await ctx.send("I'm not playing any song.")

	@commands.command(pass_context=True)
	async def resume(self, ctx):
		voice_client = utils.get(self.bot.voice_clients, guild = ctx.guild)
		if voice_client.is_paused():
			voice_client.resume()
		else:
			await ctx.send("Unable to pause the song.")

	@commands.command(pass_context=True)
	async def stop(self, ctx):
		voice_client = utils.get(self.bot.voice_clients, guild = ctx.guild)
		voice_client.stop()
		del self.play_states[guild.id]


	def play_next(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		if self.play_states[guild.id]['queue']:

			song_info = self.play_states[guild.id]['queue'].pop(0)
			self.play_states[guild.id]['current'] = song_info

			voice_client.play(FFmpegPCMAudio(song_info['url'], **self.FFMPEG_OPTIONS), after = lambda e: self.play_next(ctx))

		else:
			self.play_states[guild.id]['playing'] = False

	async def play(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		if self.play_states[guild.id]['queue']:

			self.play_states[guild.id]['playing'] = True

			song_info = self.play_states[guild.id]['queue'].pop(0)
			self.play_states[guild.id]['current'] = song_info

			voice_client.play(FFmpegPCMAudio(song_info['url'], **self.FFMPEG_OPTIONS), after = lambda e: self.play_next(ctx))

		else:
			await ctx.send("There are no songs in the queue.")


	@commands.command(pass_context=True)
	async def skip(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		voice_client.stop()

		if self.play_states[guild.id]['queue']:

			self.play_states[guild.id]['playing'] = True

			song_info = self.play_states[guild.id]['queue'].pop(0)
			self.play_states[guild.id]['current'] = song_info

			voice_client.play(FFmpegPCMAudio(song_info['url'], **self.FFMPEG_OPTIONS), after = lambda e: self.play_next(ctx))

		else:
			await ctx.send("There are no songs in the queue.")




	def getSongInfo(self, keyword: str) -> dict:

		if not self.ydl: self.loadYDL()

		try:
			result = self.ydl.extract_info("ytsearch:%s" % keyword, download=False)['entries'][0]
			return {'title': result['title'], 'url': result['formats'][0]['url']}
		except Exception:
			return None






	def inSameVoiceChannel(self, author_voice_state: discord.VoiceState, bot_voice_client: discord.VoiceClient)-> bool:

		return author_voice_state.channel and bot_voice_client and author_voice_state.channel == bot_voice_client.channel





	

		