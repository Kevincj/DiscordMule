#!/usr/bin/python3

import copy
import aiogram
import asyncio
import discord
import logging
import pymongo
import configparser
from discord.ext import commands
# from telegram.ext import Updater
from collections import defaultdict
# from telegram.ext import CommandHandler
from template import TELEGRAM_TEMPLATE, TWEET_TEMPLATE, TWITTER_TEMPLATE
from aiogram import Bot, Dispatcher, executor, types

class TelegramBot(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db


		self.tel_bot = Bot(token=self.config["Telegram"]["token"])
		self.dispatcher = Dispatcher(self.tel_bot)
		self.commands = {}

		self.telegram_cache = defaultdict(lambda : defaultdict(lambda : None))



	@commands.Cog.listener() 
	async def on_ready(self):
		await self.update_sync_status()


	async def update_sync_status(self):
		sync_needed = False
		for entry in self.db["telegram_info"].find({}): 
			if entry["tl_channel"]:
				self.bot.get_cog("Twitter").sync_status[(entry["user_id"], entry["guild_id"])]["timeline_info"]["telegram"] = True
				sync_needed = True
			if entry["self_like_channel"]:
				self.bot.get_cog("Twitter").sync_status[(entry["user_id"], entry["guild_id"])]["self_like_info"]["telegram"] = True
				sync_needed = True
			if entry["focus_channel"]:
				self.bot.get_cog("Twitter").sync_status[(entry["user_id"], entry["guild_id"])]["focus_info"]["telegram"] = True
				sync_needed = True
			if entry["like_channel"]:
				self.bot.get_cog("Twitter").sync_status[(entry["user_id"], entry["guild_id"])]["like_info"]["telegram"] = True
				sync_needed = True
			if entry["list_channel"]:
				self.bot.get_cog("Twitter").sync_status[(entry["user_id"], entry["guild_id"])]["list_info"]["telegram"] = True
				sync_needed = True
			pass
		if sync_needed: 
			await self.bot.get_cog("Twitter").sync.start()



	


	async def bindTelegram(self, ctx: commands.Context, channel_type: str, arg: str):
		if self.config["Discord"]["HandleCommands"] != "True": return

		logging.info("Binding Telegram %s channel..." % channel_type)

		author = ctx.message.author


		query_result = self.db["telegram_info"].find_one({"user_id": str(author.id), "guild_id": str(ctx.guild.id)})
		
		if query_result:
			self.db["telegram_info"].update_one(query_result, {"$set": {channel_type: arg}})

		else:
			entry = copy.deepcopy(TELEGRAM_TEMPLATE)
			entry["user_id"] = str(author.id)
			entry["guild_id"] = str(ctx.guild.id)
			entry[channel_type] = arg
			self.db["telegram_info"].insert_one(entry)

		self.telegram_cache[(str(author.id), str(ctx.guild.id))][channel_type] = arg




	@commands.command(pass_context=True, help="bind telegram like channel")
	async def bindLikeTelegram(self, ctx: commands.Context, *, arg:str):
		if self.config["Discord"]["HandleCommands"] != "True": return

		await self.bindTelegram(ctx, "like_channel", arg)



	@commands.command(pass_context=True, help="bind telegram list channel")
	async def bindListTelegram(self, ctx: commands.Context, *, arg:str):
		if self.config["Discord"]["HandleCommands"] != "True": return

		await self.bindTelegram(ctx, "list_channel", arg)




	@commands.command(pass_context=True, help="bind telegram focus channel")
	async def bindFocusTelegram(self, ctx: commands.Context, *, arg:str):
		if self.config["Discord"]["HandleCommands"] != "True": return

		await self.bindTelegram(ctx, "focus_channel", arg)



	@commands.command(pass_context=True, help="bind telegram timeline channel")
	async def bindTimelineTelegram(self, ctx: commands.Context, *, arg:str):
		if self.config["Discord"]["HandleCommands"] != "True": return

		await self.bindTelegram(ctx, "tl_channel", arg)

	@commands.command(pass_context=True, help="bind telegram self-like channel")
	async def bindTimelineTelegram(self, ctx: commands.Context, *, arg:str):
		if self.config["Discord"]["HandleCommands"] != "True": return

		await self.bindTelegram(ctx, "self_like_channel", arg)



	def get_telegram_channel(self, user_id: str, guild_id: str, channel_type: str):


		if (user_id, guild_id) in self.telegram_cache.keys():
			return self.telegram_cache[(user_id, guild_id)][channel_type]

		else:
			query_result = self.db["telegram_info"].find_one({"user_id": user_id, "guild_id": guild_id})
			if not query_result: return None

			return query_result[channel_type]




	# async def sendMessage(self, ctx: commands.Context, content: str):

	# 	target_channel = self.checkBindingStatus(ctx)

	# 	if not target_channel:
	# 		# await ctx.send("No channel found, please bind your Telegram channel.")
	# 		return
			
	# 	await self.tel_bot.send_message(chat_id="@"+target_channel, text=content)



	async def send_medias(self, author_id: str, guild_id: str, medias: list, tweet_info: str, channel_type = None):

		if len(medias) == 0: return

		if channel_type == "timeline_info":
			target_channel = self.get_telegram_channel(author_id, guild_id, "tl_channel")
		elif channel_type == "like_info":
			target_channel = self.get_telegram_channel(author_id, guild_id, "like_channel")
		elif channel_type == "list_info":
			target_channel = self.get_telegram_channel(author_id, guild_id, "list_channel")
		elif channel_type == "focus_info":
			target_channel = self.get_telegram_channel(author_id, guild_id, "focus_channel")
		elif channel_type == "self_like_info":
			target_channel = self.get_telegram_channel(author_id, guild_id, "self_like_channel")
		else:
			return

		# logging.info("Sending to: %s" % target_channel)
		
		if len(medias) == 1:
			# logging.info("Sending single media...")
			media_list = medias[0]
			j = len(media_list) - 1
			retry = 0
			while j >= 0:
				media, isVideo = media_list[j]
				try:
					if isVideo:
						await self.tel_bot.send_video(chat_id="@"+target_channel, video=media, caption = tweet_info)
					else:
						await self.tel_bot.send_photo(chat_id="@"+target_channel, photo=media, caption = tweet_info)
					break
				except aiogram.utils.exceptions.BadRequest as err:
					logging.error("Bad Request: %s" % media)
					j -= 1
				# except asyncio.TimeoutError:
				# 	logging.error("Timeout Error")
				# 	await asyncio.sleep(10)
				# 	continue
				except aiogram.utils.exceptions.TelegramAPIError as err:
					logging.error("Error INFO: %s" % str(err.args))
					if str(err.args) == "Bad Gateway":
						if retry > 5:
							logging.error("Max trials. Popping...")
							medias.pop(0)
							retry = 0
							continue
						retry += 1
						logging.error("Bad Gateway")
						await asyncio.sleep(10)
						continue
					raise err
			return


		media_group = types.MediaGroup()

		for i, media_list in enumerate(medias):
			media, isVideo = media_list[0]
			# print(media, isVideo)
			if i: 
				if isVideo:
					media_group.attach_video(media)
				else:
					media_group.attach_photo(media)
			else:
				if isVideo:
					media_group.attach_video(media, tweet_info)
				else:
					media_group.attach_photo(media, tweet_info)
		
		group_retry = 0
		while True:
			try:
				# logging.info("Sending multiple medias...")
				await self.tel_bot.send_media_group(chat_id="@"+target_channel, media=media_group)
				return
			except aiogram.utils.exceptions.BadRequest as err:
				logging.error("Bad Request: %s" % medias)
				retry = 0
				while medias:
					media_list = [medias[0]]
					try:
						await self.send_medias(author_id, guild_id, [media_list], tweet_info, channel_type)
						medias.pop(0)
						await asyncio.sleep(1)
						retry = 0
					except aiogram.utils.exceptions.RetryAfter as err:
						logging.error("Try again in %d seconds." % err.timeout)
						await asyncio.sleep(err.timeout)
					except aiogram.utils.exceptions.TelegramAPIError as err:
						logging.error("Error INFO: %s" % str(err.args))
						if str(err.args) == "Bad Gateway":
							if retry > 5:
								logging.error("Max trials. Popping...")
								medias.pop(0)
								retry = 0
								continue
							retry += 1
							logging.error("Bad Gateway")
							await asyncio.sleep(10)
							continue
						raise err
					except:
						medias.pop(0)
				return

			# except asyncio.TimeoutError:
			# 	logging.error("Timeout Error")
			# 	await asyncio.sleep(10)
			# 	continue
			except aiogram.utils.exceptions.TelegramAPIError as err:
				logging.error("Error INFO: %s" % str(err.args))
				if str(err.args) == "Bad Gateway":
					if group_retry > 5:
						logging.error("Max trials. Popping...")
						medias.pop(0)
						group_retry = 0
						continue
					group_retry += 1
					logging.error("Bad Gateway")
					await asyncio.sleep(10)
					continue
				raise err
