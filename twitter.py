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
from template import TWEET_TEMPLATE, TWITTER_TEMPLATE, INFO_TEMPLATE





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
		self.user_link_pattern = re.compile("https?:\/\/(www\.)?twitter.com\/(\w*)$")
		self.list_link_pattern = re.compile("https?:\/\/(www\.)?twitter.com\/i\/lists\/(\w*)$")


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
		'''
		Authorize the user using token info in the database

		:param user_id: id of the user
		:param guild_id: id of the guild
		:return: an API object if successful, None otherwise
		'''
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


	def updateDatabase(self, user_id: str, guild_id: str, category: str, latest_id: int = 0, push_to_discord: bool = False, sync_to_telegram: bool = False, update_min: bool = False, update_max: bool = False, sub_category: str = None):
		query_result = self.queryTwitterInfo(user_id, guild_id, category)
		# logging.info(query_result)

		if category == "timeline_info":
			if push_to_discord:
				if update_min:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.min_id" % (category): latest_id}})
				if update_max:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.max_id" % (category): latest_id}})
			elif sync_to_telegram:
				if update_min:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.min_sync_id" % (category): latest_id}})
				if update_max:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.max_sync_id" % (category): latest_id}})
		else:
			if push_to_discord:
				if update_min:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.min_id" % (category, sub_category): latest_id}})
				if update_max:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.max_id" % (category, sub_category): latest_id}})
			elif sync_to_telegram:
				if update_min:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.min_sync_id" % (category, sub_category): latest_id}})
				if update_max:
					self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.max_sync_id" % (category, sub_category): latest_id}})



	async def pushTweets(self, tweets: list[tweepy.models.Status], user_id: str, guild_id: str, category: str, sub_category: str, update_min: bool = False, update_max: bool = False, push_to_discord: bool = False, sync_to_telegram: bool = False):

		tweet_ct = 0
		current_id = None
		for tweet in tweets:
				
			re_result = self.url_pattern.search(tweet.text)
			if not re_result:
				continue
			
			tweet_link = re_result[1]
			screen_name = tweet.user.screen_name

			current_id = tweet.id

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

						elif media["type"] == "photo":
							url = media["media_url"]
							media_list.append([(url, False)])


			if len(media_list) == 0: continue
			# logging.info("Medias: %s" % media_list)

			if push_to_discord:
				logging.info("Pushing to discord channel...")
				for media in media_list:
					await ctx.send(media[0][0])

			if sync_to_telegram:

				if self.sync_status[(user_id, guild_id)][category]:

					# logging.info("Sync to Telegram... %s" % tweet_link)

					success = False
					# skipped = False
					while not success:
						# logging.info(media_list)
						try:
							await self.bot.get_cog("TelegramBot").sendMedias(user_id, guild_id, media_list, "%s from @%s" % (tweet_link, screen_name), category)
							success = True
							tweet_ct += 1
							await asyncio.sleep(1)
						except aiogram.utils.exceptions.RetryAfter as err:

							logging.info("Finished %d tweets. Try again in %d seconds. Updating [%s-%s] info to database..."% (tweet_ct, err.timeout, category, sub_category))
							# logging.info("current_id %d on %s" % (current_id, "min" if update_min else "max"))
							self.updateDatabase(user_id, guild_id, category, current_id, push_to_discord, sync_to_telegram, update_min, update_max, sub_category)

							await asyncio.sleep(err.timeout)

						# except aiogram.utils.exceptions.BadRequest as err:
							# logging.error("Bad Request. Skipped.")
							# logging.error(err)
							# skpped = True
				
				
		logging.info("Finished %d tweets. Updating [%s-%s] info to database..." % (tweet_ct, category, sub_category))					
		# logging.info("current_id %d on %s" % (current_id, "min" if update_min else "max"))
		self.updateDatabase(user_id, guild_id, category, current_id, push_to_discord, sync_to_telegram, update_min, update_max, sub_category)


	async def getTweets(self, user_id: str, guild_id: str, category: str, ctx: commands.Context = None, push_to_discord: bool = False, sync_to_telegram: bool = False, reverse: bool = False):
		'''
		Retrieve tweets from lists / likes / focused users / timeline

		:param user_id: id of the user
		:param guild_id: id of the guild
		:param ctx: context info of discord
		:push_to_discord: flag of whether to push the retrieved tweets to discord
		:push_to_telegram: flag of whether to push the retrieved tweets to telegram
		:reverse: retrieving strategy for the next api call. Default: retrieving the latest tweets (reverse = false)
		:return: None
		'''
		MAX_DISCORD_COUNT, MAX_TELEGRAM_COUNT = 50, 200

		if not (push_to_discord or sync_to_telegram): return




		logging.info("Fetching Twitter connection...")
		api = self.getAPI(user_id, guild_id)
		if not api:
			# await ctx.send("Twitter connection failed, please reconnect your Twitter account.")
			return


		match category:
			case "timeline_info":
				logging.info("Acquiring timeline...")
				query_result = self.queryTwitterInfo(user_id, guild_id, category)

				update_max, update_min = False, False

				if push_to_discord:
					max_id = query_result[category]["max_id"]
					min_id = query_result[category]["min_id"]

				else:
					max_id = query_result[category]["max_sync_id"]
					min_id = query_result[category]["min_sync_id"]
				
				max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

				if reverse and min_id > 0:
					update_min = True
					tweets = list(tweepy.Cursor(api.home_timeline, max_id = min_id - 1, count= max_count, exclude_replies = True).items())
				elif (not reverse) and max_id > 0:
					update_max = True
					tweets = list(tweepy.Cursor(api.home_timeline, since_id = max_id, count= max_count, exclude_replies = True).items())
				else:
					reverse, update_min = True, True
					tweets = list(tweepy.Cursor(api.home_timeline, count= max_count, exclude_replies = True).items())

					query_result = self.queryTwitterInfo(user_id, guild_id, category)
					self.db["twitter_info"].update_one(query_result, {"$set": {"timeline_info.max_sync_id": tweets[0].id}})


				if len(tweets) == 0: 
					logging.info("Nothing fetched, continue.")
					exit()

				logging.info("Fetched %d tweets" % len(tweets))

				if not reverse: tweets = tweets[::-1]

				await self.pushTweets(tweets, user_id, guild_id, category, None, update_min, update_max, push_to_discord, sync_to_telegram)

			case "focus_info":
				logging.info("Acquiring focused users...")
				query_result = self.queryTwitterInfo(user_id, guild_id, category)

				update_max, update_min = False, False
				print(query_result[category])
				for user_name, sync_info in query_result[category].items():

					if push_to_discord:
						max_id, min_id = sync_info["max_id"], sync_info["min_id"]

					elif sync_to_telegram:
						max_id, min_id = sync_info["max_sync_id"], sync_info["min_sync_id"]
					
					max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

					if reverse and min_id > 0:
						update_min = True
						tweets = list(tweepy.Cursor(api.user_timeline, screen_name = user_name, max_id = min_id - 1, count= max_count, exclude_replies = True).items())
					elif (not reverse) and max_id > 0:
						update_max = True
						tweets = list(tweepy.Cursor(api.user_timeline, screen_name = user_name, since_id = max_id, count= max_count, exclude_replies = True).items())
					else:
						reverse, update_min = True, True
						tweets = list(tweepy.Cursor(api.user_timeline, screen_name = user_name, count= max_count, exclude_replies = True).items())

						query_result = self.queryTwitterInfo(user_id, guild_id, category)
						self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.max_sync_id" % (category, user_name): tweets[0].id}})

					if len(tweets) == 0: 
						logging.info("Nothing fetched, continue.")
						continue

					logging.info("Fetched %d tweets" % len(tweets))

					if not reverse: tweets = tweets[::-1]

					await self.pushTweets(tweets, user_id, guild_id, category, user_name, update_min, update_max, push_to_discord, sync_to_telegram)
		

			case "list_info":
				logging.info("Acquiring list statuses...")
				query_result = self.queryTwitterInfo(user_id, guild_id, category)

				update_max, update_min = False, False
				print(query_result[category])
				for list_id, sync_info in query_result[category].items():

					if push_to_discord:
						max_id, min_id = sync_info["max_id"], sync_info["min_id"]

					elif sync_to_telegram:
						max_id, min_id = sync_info["max_sync_id"], sync_info["min_sync_id"]
					
					max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

					if reverse and min_id > 0:
						update_min = True
						tweets = list(tweepy.Cursor(api.list_timeline, list_id = list_id, max_id = min_id - 1, count= max_count).items())
					elif (not reverse) and max_id > 0:
						update_max = True
						tweets = list(tweepy.Cursor(api.list_timeline, list_id = list_id, since_id = max_id, count= max_count).items())
					else:
						reverse, update_min = True, True
						tweets = list(tweepy.Cursor(api.list_timeline, list_id = list_id, count= max_count).items())

						query_result = self.queryTwitterInfo(user_id, guild_id, category)
						self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.max_sync_id" % (category, list_id): tweets[0].id}})

					if len(tweets) == 0: 
						logging.info("Nothing fetched, continue.")
						continue

					logging.info("Fetched %d tweets" % len(tweets))

					if not reverse: tweets = tweets[::-1]

					await self.pushTweets(tweets, user_id, guild_id, category, list_id, update_min, update_max, push_to_discord, sync_to_telegram)
		
			case "like_info":
				logging.info("Acquiring list statuses...")
				query_result = self.queryTwitterInfo(user_id, guild_id, category)

				update_max, update_min = False, False
				print(query_result[category])
				for user_name, sync_info in query_result[category].items():

					if push_to_discord:
						max_id, min_id = sync_info["max_id"], sync_info["min_id"]

					elif sync_to_telegram:
						max_id, min_id = sync_info["max_sync_id"], sync_info["min_sync_id"]
					
					max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

					if reverse and min_id > 0:
						update_min = True
						tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, max_id = min_id - 1, count= max_count).items())
					elif (not reverse) and max_id > 0:
						update_max = True
						tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, since_id = max_id, count= max_count).items())
					else:
						reverse, update_min = True, True
						tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, count= max_count).items())

						query_result = self.queryTwitterInfo(user_id, guild_id, category)
						self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s.max_sync_id" % (category, user_name): tweets[0].id}})

					if len(tweets) == 0: 
						logging.info("Nothing fetched, continue.")
						continue

					logging.info("Fetched %d tweets" % len(tweets))

					if not reverse: tweets = tweets[::-1]

					await self.pushTweets(tweets, user_id, guild_id, category, user_name, update_min, update_max, push_to_discord, sync_to_telegram)
		
				


		




	async def addByLink(self, user_id: str, guild_id: str, type_name: str, keyword: str):
		"""
		Add binding info into the database

		:param user_id: id of the user
		:param guild_id: id of the guild
		:param type_name: type of the info to add, from {"list_info", "focus_info", "like_info"}
		:param keyword: list or user's screen name
		:return: None
		"""
		query_result = self.queryTwitterInfo(user_id, guild_id, type_name)

		finished = False
		if query_result and type_name in query_result.keys():
			if keyword in query_result[type_name].keys():
				return
			
			self.db["twitter_info"].update_one(query_result, {"$set": {"%s.%s" % (type_name, keyword): INFO_TEMPLATE}})

		else:
			entry = copy.deepcopy(TWITTER_TEMPLATE)
			entry["user_id"] = str(user_id)
			entry["guild_id"] = str(guild_id)
			entry[type_name] = {keyword: INFO_TEMPLATE}
			self.db["twitter_info"].insert_one(entry)


	@commands.command(pass_context=True, help="add an account for focus tracking")
	async def addFocusByLink(self, ctx: commands.Context, *, arg: str):
		
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		logging.info("Adding to focus tracking...")

		re_result = self.user_link_pattern.search(arg)
		if not re_result:
			await ctx.send("Please provide a valid link of the twitter account.")
			return

		screen_name = re_result[2]

		await self.addByLink(user_id, guild_id, "focus_info", screen_name)



	@commands.command(pass_context=True, help="add an account for list tracking")
	async def addListByLink(self, ctx: commands.Context, *, arg: str):
		
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		logging.info("Adding to list tracking...")

		re_result = self.list_link_pattern.search(arg)
		if not re_result:
			await ctx.send("Please provide a valid link of the twitter list.")
			return

		list_id = re_result[2]

		await self.addByLink(user_id, guild_id, "list_info", list_id)



	@commands.command(pass_context=True, help="add an account for like tracking")
	async def addLikeByLink(self, ctx: commands.Context, *, arg: str):
		
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		logging.info("Adding to like tracking...")

		re_result = self.user_link_pattern.search(arg)
		if not re_result:
			await ctx.send("Please provide a valid link of the twitter account.")
			return

		screen_name = re_result[2]

		await self.addByLink(user_id, guild_id, "like_info", screen_name)




	@commands.command(pass_context=True, help="grab medias from your Twitter timeline")
	async def timeline(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		await self.getTweets(user_id, guild_id, "timeline_info", ctx, push_to_discord= True)


	@commands.command(pass_context=True, help="grab medias from your Twitter timeline (older than recorded)")
	async def timelineReverse(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		await self.getTweets(user_id, guild_id, "timeline_info", ctx, push_to_discord= True, reverse = True)


	@tasks.loop(minutes=60)
	async def sync(self):

		logging.info("Sync...")
		# logging.info(self.sync_status)
		for key, channel_status in self.sync_status.items():
			# logging.info(channel_status)
			if channel_status["timeline_info"]:
				await self.getTweets(key[0], key[1], "timeline_info", sync_to_telegram= True)
			if channel_status["focus_info"]:
				await self.getTweets(key[0], key[1], "focus_info", sync_to_telegram= True)
			if channel_status["like_info"]:
				await self.getTweets(key[0], key[1], "like_info", sync_to_telegram= True)
			if channel_status["list_info"]:
				await self.getTweets(key[0], key[1], "list_info", sync_to_telegram= True)
		logging.info("Finished sync.")



	@commands.command(pass_context=True)
	async def syncLikes(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(user_id, guild_id, "like_channel"):
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

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(user_id, guild_id, "list_channel"):
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

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(user_id, guild_id, "tl_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return


		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_status[(user_id, guild_id)]["timeline_info"] = True

		if not self.sync.is_running():
			self.sync.start()

	@commands.command(pass_context=True)
	async def syncTimelineReverse(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(user_id, guild_id, "tl_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Retrieving older tweets in timeline...")
		await self.getTweets(user_id, guild_id, "timeline_info", None, sync_to_telegram= True, reverse = True)