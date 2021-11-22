#!/usr/bin/python3

import re
import copy
import tweepy
import aiogram
import asyncio
import discord
import logging
import pymongo
import configparser
from discord.ext import tasks
from discord.ext import commands
from collections import defaultdict
from template import TWEET_TEMPLATE, TWITTER_TEMPLATE





class Twitter(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db

		self.apis = defaultdict(lambda: None)

		self.binding_auths = defaultdict(lambda: None)
		self.bounded_auths = defaultdict(lambda: None)

		self.sync_status = defaultdict(lambda: defaultdict(lambda: False))

		self.url_pattern = re.compile("(https?:..t.co.\w+)$")


		self.RATE_LIMIT_TL = 15

	@commands.command(pass_context=True, help="request a Twitter connection")
	async def connectTwitter(self, ctx: commands.Context):

		author = ctx.message.author

		
		query_result = self.queryTwitterInfo(user_id, guild_id, "tweet_token")
		if query_result:
			self.db["twitter_info"].update_one(query_result, {"$set": {"tweet_token": None}})

		auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])

		await ctx.send("Please authorize via the following link: %s\n\
			And use \"=bindTwitter your_verifier\" to bind your Twitter account." % auth.get_authorization_url())
		self.binding_auths[author.id] = auth



	@commands.command(pass_context=True, help="bind Twitter account")
	async def bindTwitter(self, ctx: commands.Context, *, arg: str):
		
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.binding_auths[author.id]:
			await ctx.send("Please use \"=connectTwitter\" first to request a token before binding.")
			return

		query_result = self.queryTwitterInfo(user_id, guild_id, "tweet_token")
		access_token, access_secret = self.binding_auths[author.id].get_access_token(arg)
		if not (access_token and access_secret):
			await ctx.send("Invalid verifier, please try again.")
			return

		if query_result:
			self.db["twitter_info"].update_one(query_result, {"$set": {
					"tweet_token.access_token": access_token,
					"tweet_token.access_secret": access_secret
				}})
		else:
			entry = copy.deepcopy(TWITTER_TEMPLATE)
			entry["user_id"] = user_id
			entry["guild_id"] = guild_id
			entry["tweet_token"] = {
						"access_token": access_token,
						"access_secret": access_secret
					}
			self.db["twitter_info"].insert_one(entry)

		self.binding_auths[author.id].set_access_token(access_token, access_secret)
		self.bounded_auths[author.id] = tweepy.API(self.binding_auths[author.id])
		self.binding_auths[author.id] = None

		await ctx.send("Successfully bounded to your Twitter account.")





	def getAPI(self, user_id, guild_id):
		if not self.apis[(user_id, guild_id)]:

			query_result = self.queryTwitterInfo(user_id, guild_id, "tweet_token")
			# logging.info(query_result)
			if query_result:
				
				logging.info("Setting up Twitter connection...")
				auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])
				auth.set_access_token(query_result["tweet_token"]["access_token"], query_result["tweet_token"]["access_secret"])
				api = tweepy.API(auth)

		else:
			api = self.apis[(user_id, guild_id)]
			
		if api:
			self.apis[(user_id, guild_id)] = api

		return api



	def queryTwitterInfo(self, user_id, guild_id, fields):
		if type(fields) == str:
			fields_dict = {fields: 1}
		else:
			fields_dict = {field: 1 for field in fields}
		fields_dict["user_id"] = 1
		fields_dict["guild_id"] = 1
		# logging.info("Querying %s, %s, %s" % (user_id, guild_id, fields_dict))
		return self.db["twitter_info"].find_one({"user_id": user_id, "guild_id": guild_id}, fields_dict)


	async def getTimeline(self, user_id: str, guild_id: str, ctx: commands.Context = None, push_to_discord = False, sync_to_telegram = False, reverse = False) -> None:
		
		MAX_DISCORD_COUNT, MAX_TELEGRAM_COUNT = 50, 200

		tweet_ct = 0
		if not (push_to_discord or sync_to_telegram): return

		logging.info("Fetching Twitter connection...")
		api = self.getAPI(user_id, guild_id)
		if not api:
			# await ctx.send("Twitter connection failed, please reconnect your Twitter account.")
			return

		logging.info("Acquiring timeline...")
		query_result = self.queryTwitterInfo(user_id, guild_id, "timeline_info")

		update_max, update_min = False, False

		if push_to_discord:
			max_id = query_result["timeline_info"]["max_id"] if "max_id" in query_result["timeline_info"].keys() else 0
			min_id = query_result["timeline_info"]["min_id"]  if "min_id" in query_result["timeline_info"].keys() else 0

		else:
			max_id = query_result["timeline_info"]["max_sync_id"]  if "max_sync_id" in query_result["timeline_info"].keys() else 0
			min_id = query_result["timeline_info"]["min_sync_id"]  if "min_sync_id" in query_result["timeline_info"].keys() else 0
		
		max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT


		while True:

			if reverse and min_id > 0:
				tweets = api.home_timeline(max_id = min_id - 1, count= max_count, exclude_replies = True)
				update_min = True
			elif (not reverse) and max_id > 0:
				tweets = api.home_timeline(since_id = max_id, count= max_count, exclude_replies = True)
				update_max = True
			else:
				reverse, update_min = True, True
				tweets = api.home_timeline(count= max_count, exclude_replies = True)
				if len(tweets) > 0: 
					query_result = self.queryTwitterInfo(user_id, guild_id, "timeline_info")
					self.db["twitter_info"].update_one(query_result, {"$set": {"timeline_info.max_sync_id": tweets[0].id}})

			if len(tweets) == 0: break
			logging.info("Fetched %d tweets" % len(tweets))

			max_id = tweets[0].id
			for tweet in tweets:

				re_result = self.url_pattern.search(tweet.text)
				if not re_result:
					continue
				
				tweet_link = re_result[1]
				screen_name = tweet.user.screen_name


				min_id = tweet.id

				media_list = []
				if hasattr(tweet, "extended_entities"):
					extended_entities = tweet.extended_entities
					if "media" in extended_entities.keys():
						media_list = []
						for media in extended_entities["media"]:
							if media["type"] == "video":
								videos = {}
								video_vars = media["video_info"]["variants"]
								for var in video_vars:
									if var["content_type"] == "video/mp4":
										videos[var["bitrate"]] = var["url"]
								media_list.append([(videos[bitrate], True) for bitrate in sorted(videos.keys(), reverse=True)])
								# logging.info("Video")
							elif media["type"] == "photo":
								url = media["media_url"]
								media_list.append([(url, False)])
								# logging.info("Photo")

				if len(media_list) == 0: continue
				# logging.info("Medias: %s" % media_list)

				if push_to_discord:
					logging.info("Pushing to discord channel...")
					for media in media_list:
						await ctx.send(media[0][0])

				if sync_to_telegram:

					if self.sync_status[(user_id, guild_id)]["timeline"]:

						# logging.info("Sync to Telegram... %s" % tweet_link)

						success = False
						# skipped = False
						while not success:
							# logging.info(media_list)
							try:
								await self.bot.get_cog("TelegramBot").sendMedias(user_id, guild_id, media_list, "%s from @%s" % (tweet_link, screen_name), "timeline")
								success = True
								tweet_ct += 1
								await asyncio.sleep(1)
							except aiogram.utils.exceptions.RetryAfter as err:
								logging.error("Reached limit while processing %5d... Try again in %d seconds" % (tweet_ct, err.timeout))
								await asyncio.sleep(err.timeout)
							# except aiogram.utils.exceptions.BadRequest as err:
								# logging.error("Bad Request. Skipped.")
								# logging.error(err)
								# skpped = True


					
			logging.info("Finished %d tweets. Updating timeline info to database..." % tweet_ct)
			query_result = self.queryTwitterInfo(user_id, guild_id, "timeline_info")
			if push_to_discord:
				if update_min:
					self.db["twitter_info"].update_one(query_result, {"$set": {"timeline_info.min_id": min_id}})
				if update_max:
					self.db["twitter_info"].update_one(query_result, {"$set": {"timeline_info.max_id": max_id}})
			else:
				if update_min:
					self.db["twitter_info"].update_one(query_result, {"$set": {"timeline_info.min_sync_id": min_id}})
				if update_max:
					self.db["twitter_info"].update_one(query_result, {"$set": {"timeline_info.max_sync_id": max_id}})

			# logging.info(self.queryTwitterInfo(user_id, guild_id, "timeline_info"))

			# query_result = self.queryTwitterInfo(user_id, guild_id, "timeline_info")
			# logging.info(query_result)




	@commands.command(pass_context=True, help="grab medias from your Twitter timeline")
	async def timeline(self, ctx: commands.Context):

		await self.getTimeline(ctx, push_to_discord= True)



	@tasks.loop(minutes=180)
	async def sync(self):

		logging.info("Sync...")
		# logging.info(self.sync_status)
		for key, channel_status in self.sync_status.items():
			# logging.info(channel_status)
			timeline_status = channel_status["timeline"]
			if timeline_status:
				await self.getTimeline(user_id = key[0], guild_id = key[1], sync_to_telegram= True)

		logging.info("Finished sync.")



	@commands.command(pass_context=True)
	async def syncLikes(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(ctx, "like_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_likes_context[(user_id, guild_id)] = ctx

		if not self.sync.is_running():
			self.sync.start()



	@commands.command(pass_context=True)
	async def syncLists(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(ctx, "list_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_lists_context[(user_id, guild_id)] = ctx

		if not self.sync.is_running():
			self.sync.start()



	@commands.command(pass_context=True)
	async def syncTimeline(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(ctx, "tl_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return


		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_status[(user_id, guild_id)]["timeline"] = True

		if not self.sync.is_running():
			self.sync.start()


	@commands.command
	async def sayHiFromTwitterCog(self, ctx: commands.Context):
		await self.bot.get_cog("General").hi(ctx)
