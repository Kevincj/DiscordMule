#!/usr/bin/python3

import re
import time
import random
import typing
import asyncio
import discord
import logging
import pymongo
import pyttsx3
import spotipy
import datetime
import functools
import youtube_dl
import configparser
import discord.utils as utils
from discord.ext import commands
from youtube_dl import YoutubeDL
from discord import FFmpegPCMAudio
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from spotipy.oauth2 import SpotifyClientCredentials



class Voice(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):

		self.bot = bot
		self.config = config
		self.db = db

		self.engine = None
		self.spotify = None



		self.playing = False
		self.ydl = None
		self.play_states = defaultdict(lambda: {"playing": False, "queue": [], "current": None})
		self.FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}
		self.link_pattern = re.compile("^http*", re.IGNORECASE)
		self.spotify_playlist_pattern = re.compile("^http.*//.*spotify.*playlist.*/(.*)", re.IGNORECASE)
		self.spotify_artist_pattern = re.compile("^http.*//.*spotify.*artist.*/(.*)", re.IGNORECASE)
		self.q_display_count = 5

		self.load_tts()
		self.load_ydl()
		self.load_spotify()


		
	def load_tts(self) -> None:

		logging.info("Loading TTS...")

		self.engine = pyttsx3.init("espeak")

		for voice in self.engine.getProperty("voices"):

			if "Mandarin" in voice.id:

				logging.info("Setting voice as: %s" % voice.id)
				self.engine.setProperty("voice", voice.id)
				break

		self.engine.setProperty("rate", 145)
		
		# self.engine.save_to_file("OK", "tmp.mp3")
		# self.engine.runAndWait()



	def load_ydl(self) -> None:

		logging.info("Loading youtube_dl...")

		YDL_OPTIONS = {
						"format": "bestaudio", 
						# "noplaylist":"True"
						}
		self.ydl = YoutubeDL(YDL_OPTIONS)



	def load_spotify(self) -> None:

		logging.info("Setting up Spotify access...")
		self.spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=self.config["Spotify"]["ClientID"],
                                                           client_secret=self.config["Spotify"]["ClientSecret"]))

		if self.spotify:
			logging.info("Connected to Spotify successfullly.")
		else:
			logging.error("Failed to connect to Spotify.")



	@commands.command(pass_context=True, help="join voice channel")
	async def join(self, ctx: commands.Context):

		logging.info("Received -join request from %s" % ctx.author)

		if not ctx.author.voice:
			return await ctx.send("Please join a voice channel before running this command.")

		voice_client = utils.get(ctx.bot.voice_clients, guild = ctx.guild)

		if voice_client and voice_client.is_connected():

			if ctx.author.voice.channel == voice_client.channel: return

			logging.info("Disconnecting current voice channel...")
			await ctx.voice_client.disconnect()

		logging.info("Joining voice channel...")
		await ctx.author.voice.channel.connect()
			


	@commands.command(pass_context=True, help="leave voice channel")
	async def leave(self, ctx: commands.Context):

		logging.info("Received -leave request from %s" % ctx.author)

		voice_client = utils.get(ctx.bot.voice_clients, guild = ctx.guild)

		if voice_client:
			await voice_client.disconnect()
			del self.play_states[ctx.guild.id]

		else:
			await ctx.send("I'm not in any voice channel of this server.")



	# @commands.command(pass_context=True, help="TTS from bot")
	# async def say(self, ctx: commands.Context, *, arg: str):
		
	# 	logging.info("Received -say request from %s: %s" % (ctx.author, arg))

	# 	if not ctx.author.voice:
	# 		return await ctx.send("Please join a voice channel before running this command.")

	# 	voice_client = utils.get(ctx.bot.voice_clients, guild = ctx.guild)

	# 	if not self.in_same_discord_channel(ctx.author.voice, ctx.voice_client):
	# 		return await ctx.send("I'm not in your voice channel.")

	# 	print(arg, type(arg))
	# 	self.engine.save_to_file(arg, "tmp.mp3")
	# 	self.engine.runAndWait()
	# 	return voice_client.play(FFmpegPCMAudio("tmp.mp3"))



	@commands.command(pass_context=True, help="show queue")
	async def q(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		if not self.play_states[guild.id]["current"]:
			return await ctx.send("Music queue is empty.")

		embed = discord.Embed(
			title="Showing next %d songs:" % self.q_display_count
		)
		embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
		embed.add_field(
			name = "Currently playing",
			value = self.play_states[guild.id]["current"]["title"] if self.play_states[guild.id]["current"] else "None",
			inline = False
		)
		if self.play_states[guild.id]["queue"]:
			embed.add_field(
				name="Next up",
				value="\n".join(" - %s" % song_info["title"] for song_info in self.play_states[guild.id]["queue"][:self.q_display_count]),
				inline=False
			)
		else:
			embed.add_field(
				name="Next up",
				value=" - None",
				inline=False
			)

		msg = await ctx.send(embed=embed)



	@commands.command(pass_context=True, help="clear queue")
	async def clear(self, ctx: commands.Context):

		logging.info("Clearing queue...")
		self.play_states[ctx.guild.id]["queue"] = []

		await ctx.send("Queue is empty now.")



	@commands.command(pass_context=True, help="play songs by keyword/url, spotify playlist/artist link supported")
	async def p(self, ctx: commands.Context, *, kw: str):
		print("status:", self.play_states[ctx.guild.id])

		if not ctx.author.voice:
			return await ctx.send("Please join a voice channel before running this command.")

		if not self.in_same_discord_channel(ctx.author.voice, ctx.voice_client):
			return await ctx.send("I'm not in your voice channel.")

		# Match link patterns
		if self.spotify_playlist_pattern.search(kw):
			await ctx.send("Fetching songs from playlist...")
			result = self.spotify_playlist_pattern.search(kw)
			song_info = self.get_spotify_list(result.group(1))

		elif self.spotify_artist_pattern.search(kw):
			await ctx.send("Fetching songs from artist...")
			result = self.spotify_artist_pattern.search(kw)
			song_info = self.get_spotify_artist(result.group(1))

		elif self.link_pattern.match(kw):
			song_info = self.get_song_from_url(kw)

		else:
			song_info = self.get_song_info(kw)


		# Invalid request
		if not song_info:

			return await ctx.send("Unable to find the song/list, please try another keyword.")

		# Playlist
		if type(song_info) is dict:
			logging.info("Song found: %s", song_info)
			self.play_states[ctx.guild.id]["queue"].append(song_info)
			await ctx.send("Added %s to queue" % song_info["title"])

		# Song
		else:
			print("status:", self.play_states[ctx.guild.id])
			logging.info("Spotify playlist found: %s", result.group(1))
			self.play_states[ctx.guild.id]["queue"] += song_info
			await ctx.send("Adding songs in the playlist to queue.")

		# Start playing
		if not self.play_states[ctx.guild.id]["playing"]:
			await self.play(ctx)



	async def play_next(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		if self.play_states[guild.id]["queue"]:


			song_info = self.play_states[guild.id]["queue"].pop(0)
			if not song_info["url"]:
				song_info = self.get_song_info(song_info["title"])

			self.play_states[guild.id]["playing"] = True
			self.play_states[guild.id]["current"] = song_info
			await ctx.send("Now playing: %s" % self.play_states[guild.id]["current"]["title"])

			await voice_client.play(FFmpegPCMAudio(song_info["url"], **self.FFMPEG_OPTIONS), after = lambda e: self.play_next(ctx))

		else:
			self.play_states[guild.id]["playing"] = False



	async def play(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		if self.play_states[guild.id]["queue"]:

			song_info = self.play_states[guild.id]["queue"].pop(0)
			if not song_info["url"]:
				song_info = self.get_song_info(song_info["title"])

			self.play_states[guild.id]["playing"] = True

			
			self.play_states[guild.id]["current"] = song_info
			await ctx.send("Now playing: %s" % self.play_states[guild.id]["current"]["title"])

			voice_client.play(FFmpegPCMAudio(song_info["url"], **self.FFMPEG_OPTIONS), after = lambda e: self.play_next(ctx))

		else:
			await ctx.send("There are no songs in the queue.")



	@commands.command(pass_context=True, help="next song")
	async def skip(self, ctx: commands.Context):

		guild, voice_client = ctx.guild, ctx.voice_client

		voice_client.stop()

		if self.play_states[guild.id]["queue"]:


			song_info = self.play_states[guild.id]["queue"].pop(0)
			if not song_info["url"]:
				song_info = self.get_song_info(song_info["title"])

			self.play_states[guild.id]["playing"] = True

			self.play_states[guild.id]["current"] = song_info
			await ctx.send("Now playing: %s" % self.play_states[guild.id]["current"]["title"])

			voice_client.play(FFmpegPCMAudio(song_info["url"], **self.FFMPEG_OPTIONS), after = lambda e: self.play_next(ctx))

		else:
			await ctx.send("There are no songs in the queue.")



	@commands.command(pass_context=True, help="pause")
	async def pause(self, ctx):

		voice_client = utils.get(self.bot.voice_clients, guild = ctx.guild)

		if voice_client.is_playing():
			voice_client.pause()

		else:
			await ctx.send("I'm not playing any song.")



	@commands.command(pass_context=True, help="resume")
	async def resume(self, ctx):

		voice_client = utils.get(self.bot.voice_clients, guild = ctx.guild)

		if voice_client.is_paused():
			voice_client.resume()

		else:
			await ctx.send("Unable to pause the song.")



	@commands.command(pass_context=True, help="stop")
	async def stop(self, ctx):

		voice_client = utils.get(self.bot.voice_clients, guild = ctx.guild)
		voice_client.stop()

		del self.play_states[ctx.guild.id]
		print(self.play_states[ctx.guild.id])



	def get_spotify_artist(self, list_id: str) -> list:

		try:
			results = self.spotify.artist_top_tracks(list_id)
			song_names = [ "%s - %s" % (item["name"], item["artists"][0]["name"]) for item in results["tracks"]]
			random.shuffle(song_names)


			playlist = [{"title": song_name, "url": None} for song_name in song_names]

			return playlist

		except:
			return None



	def get_spotify_list(self, list_id: str) -> list:

		try:
			results = self.spotify.playlist(list_id)
			song_names = [ "%s - %s" % (item["track"]["name"], item["track"]["artists"][0]["name"]) for item in results["tracks"]["items"]]
			random.shuffle(song_names)

			playlist = [{"title": song_name, "url": None} for song_name in song_names]

			return playlist

		except:
			return None



	def get_song_info(self, keyword: str) -> dict:

		if not self.ydl: self.load_ydl()

		try:
			result = self.ydl.extract_info("ytsearch:%s" % keyword, download=False)["entries"][0]
			return {"title": result["title"], "url": result["formats"][0]["url"]}

		except Exception:
			return None



	def get_song_from_url(self, url: str) -> dict:

		if not self.ydl: self.load_ydl()

		try:
			result = self.ydl.extract_info(url, download=False)
			return {"title": result["title"], "url": result["formats"][0]["url"]}

		except Exception:
			return None



	def in_same_discord_channel(self, author_voice_state: discord.VoiceState, bot_voice_client: discord.VoiceClient)-> bool:

		return author_voice_state.channel and bot_voice_client and author_voice_state.channel == bot_voice_client.channel





	

		