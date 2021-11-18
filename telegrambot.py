#!/usr/bin/python3


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
from template import TWEET_TEMPLATE, USER_TEMPLATE
from aiogram import Bot, Dispatcher, executor, types

class TelegramBot(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db

		self.channel = "@" + self.config["Telegram"]["channel"]

		self.tel_bot = Bot(token=self.config["Telegram"]["token"])
		self.dispatcher = Dispatcher(self.tel_bot)
		self.commands = {}

		self.telegram_cache = {}


	# @commands.command(pass_context=True, help="activate telegram bot")
	# async def activateTelegram(self, ctx: commands.Context):

	# 	logging.info("Activating Telegram bot...")
	# 	for cmd, handler in self.commands.items():
	# 		self.dispatcher.add_handler(CommandHandler(cmd, handler))
	# 	self.updater.start_polling()



	@commands.command(pass_context=True, help="bind telegram channel")
	async def bindTimelineTelegram(self, ctx: commands.Context, *, arg:str):

		logging.info("Binding Telegram timeline channel...")

		author = ctx.message.author



		query_result = self.db["telegram_info"].find_one({"user_id": str(author.id), "guild_id": str(ctx.guild.id)})
		
		if query_result:
			self.db["telegram_info"].update_one(query_result, {"$set": {"channel": arg}})

		else:
			self.db["telegram_info"].insert_one({
					"user_id": str(author.id),
					"guild_id": str(ctx.guild.id),
					"tl_channel": arg
				})

		self.telegram_cache[(str(author.id), str(ctx.guild.id))] = arg



	def getTelegramChannel(self, ctx: commands.Context, channel: str):
		author = ctx.message.author


		if (str(author.id), str(ctx.guild.id)) in self.telegram_cache.keys():
			return self.telegram_cache[(str(author.id), str(ctx.guild.id))]

		else:
			query_result = self.db["telegram_info"].find_one({"user_id": str(author.id), "guild_id": str(ctx.guild.id)})
			if not query_result: return None

			return query_result[channel]




	async def sendMessage(self, ctx: commands.Context, content: str):

		target_channel = self.checkBindingStatus(ctx)

		if not target_channel:
			await ctx.send("No channel found, please bind your Telegram channel.")
			return
			
		await self.tel_bot.send_message(chat_id="@"+target_channel, text=content)



	async def sendMedias(self, ctx: commands.Context, medias: list, tweet_info: str, channel_type = None):

		if len(medias) == 0: return

		if channel_type == "timeline":
			target_channel = self.getTelegramChannel(ctx, "tl_channel")
		elif channel_type == "likes":
			target_channel = self.getTelegramChannel(ctx, "like_channel")
		elif channel_type == "lists":
			target_channel = self.getTelegramChannel(ctx, "list_channel")
		else:
			return

		if len(medias) == 1:
			for j in range(len(medias)-1,-1,-1):
				media, isVideo = medias[0][j]
				try:
					if isVideo:
						await self.tel_bot.send_video(chat_id="@"+target_channel, video=media, caption = tweet_info)
					else:
						await self.tel_bot.send_photo(chat_id="@"+target_channel, photo=media, caption = tweet_info)
				except aiogram.utils.exceptions.BadRequest as err:
					logging.error("Bad Request: %s" % media)
					continue
				except asyncio.TimeoutError:
					logging.error("Timeout. Passed.")
					continue
				break
			return


		media_group = types.MediaGroup()

		for i, media_list in enumerate(medias):
			media, isVideo = media_list[-1]
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
		
		try:
			await self.tel_bot.send_media_group(chat_id="@"+target_channel, media=media_group)
		except aiogram.utils.exceptions.BadRequest as err:
			logging.error("Bad Request: %s" % medias)
		except asyncio.TimeoutError:
			logging.error("Timeout. Passed.")
