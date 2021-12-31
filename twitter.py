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
from template import GUILD_TEMPLATE, TWEET_TEMPLATE, TWITTER_TEMPLATE, INFO_TEMPLATE





class Twitter(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db

		self.apis = defaultdict(lambda: None)

		self.binding_auths = defaultdict(lambda: None)
		self.bounded_auths = defaultdict(lambda: None)

		self.sync_status = defaultdict(lambda: defaultdict(lambda: {"telegram": False, "discord": False}))
		self.guild_forwarding = defaultdict(lambda: {"img": None, "vid": None})


		self.url_pattern = re.compile("(https?:..t.co.\w+)$")
		self.user_link_pattern = re.compile("https?:\/\/(www\.)?twitter.com\/(\w*)$")
		self.list_link_pattern = re.compile("https?:\/\/(www\.)?twitter.com\/i\/lists\/(\w*)$")
		self.media_forwarding_pattern = re.compile("\|\|http.+[^\|]+\|\|")


		self.CATEGORIES = ["self_like_info", "list_info", "like_info", "focus_info", "timeline_info"]

		self.RATE_LIMIT_TL = 15
  
		self.load_guild_forwarding()
		# logging.info(self.guild_forwarding)
  
	def load_guild_forwarding(self):
		for entry in self.db["guild_info"].find({}): 
			self.guild_forwarding[entry["guild_id"]]["img"] = entry["forwarding_channels"]["img"]
			self.guild_forwarding[entry["guild_id"]]["vid"] = entry["forwarding_channels"]["vid"]
			self.guild_forwarding[entry["guild_id"]]["pending"] = entry["forwarding_channels"]["pending"]
  
  
	@commands.command(pass_context=True, help="request a Twitter connection")
	async def connectTwitter(self, ctx: commands.Context):

		author = ctx.message.author

		
		query_result = self.query_twitter_info(user_id, guild_id, "tweet_token")
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

		query_result = self.query_twitter_info(user_id, guild_id, "tweet_token")
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





	def get_api(self, user_id, guild_id):
		'''
		Authorize the user using token info in the database

		:param user_id: id of the user
		:param guild_id: id of the guild
		:return: an API object if successful, None otherwise
		'''
		if not self.apis[(user_id, guild_id)]:

			query_result = self.query_twitter_info(user_id, guild_id, "tweet_token")
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



	def query_twitter_info(self, user_id, guild_id, fields):
		if type(fields) == str:
			fields_dict = {fields: 1}
		else:
			fields_dict = {field: 1 for field in fields}
		fields_dict["user_id"] = 1
		fields_dict["guild_id"] = 1
		# logging.info("Querying %s, %s, %s" % (user_id, guild_id, fields_dict))
		return self.db["twitter_info"].find_one({"user_id": user_id, "guild_id": guild_id}, fields_dict)


	@commands.command(pass_context=True, help="flush cache channel")
	async def flush(self, ctx: commands.Context = None):
     
		if ctx.channel.id == self.guild_forwarding[str(ctx.guild.id)]["pending"]:
			messages = await ctx.channel.history(limit=100).flatten()
			for message in messages:
				new_message = None
				forwarding_channels = self.guild_forwarding[str(message.guild.id)]
				media = message.content
				if message.content:
					media = message.content
				elif message.attachments:
					media = message.attachments[0].url
				else: return
				logging.info("Pending media: %s" % media)
				if self.is_image_link(media.lower()) and forwarding_channels["img"]:
					new_message = await self.bot.get_channel(forwarding_channels["img"]).send(media)
				elif self.is_video_link(media.lower()) and forwarding_channels["vid"]:
					new_message = await self.bot.get_channel(forwarding_channels["vid"]).send(media)
				await message.delete()
				await asyncio.sleep(0.3)
				
				if not new_message: return
				await new_message.add_reaction('❤️')
				await asyncio.sleep(0.3)
				await new_message.add_reaction('💩')
				await asyncio.sleep(0.3)
		logging.info("Successfully deleted %d messages." % len(messages))


	@tasks.loop(minutes=60 * 3)
	async def sync(self):

		logging.info("Sync...")

		tmp_status = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: False)))
		for key, channel_status in self.sync_status.items():
			for entry, status in channel_status.items():
				tmp_status[key][entry]["discord"] = status["discord"]
				tmp_status[key][entry]["telegram"] = status["telegram"]
 
		for key, channel_status in tmp_status.items():
			for entry, status in channel_status.items():
				if status["telegram"]:
					await self.get_tweets(key[0], key[1], entry, sync_to_telegram = True)
		for key, channel_status in tmp_status.items():
			for entry, status in channel_status.items():
				if status["discord"]:
					await self.get_tweets(key[0], key[1], entry, push_to_discord = status["discord"])
		logging.info("Finished sync.")



	def is_image_link(self, media):
		return "jpg" in media or "png" in media or "gif" in media or "webp" in media or "jpeg" in media

	def is_video_link(self, media):
		return "mp4" in media or "mov" in media or "avi" in media

	def is_twitter_message(self, message: discord.Message):
		return self.media_forwarding_pattern.match(message.content)

	def get_medias(self, message: discord.Message):
		media_list = []
     
		content = message.content
		if self.media_forwarding_pattern.match(content):
			medias = content.split("\n")[1:]
			for media in medias:
				if self.is_image_link(media.lower()):
					media_list.append((media, "img"))
				elif self.is_video_link(media.lower()):
					media_list.append((media, "vid"))
		return media_list

	def in_media_channels(self, message: discord.Message):
		return message.channel.id == self.guild_forwarding[str(message.guild.id)]["img"] or message.channel.id == self.guild_forwarding[str(message.guild.id)]["vid"]

  
	@commands.Cog.listener()
	async def on_message(self, message):
		
		if self.bot.command_prefix != "=": return
		# if message.author.id == self.bot.user.id and \
		# 	(message.channel.id not in self.guild_forwarding[str(message.guild.id)].values()) and \
		# 	self.is_twitter_message(message):
		# 	await message.add_reaction('✈️')
		# 	await asyncio.sleep(0.3)
		# 	await message.add_reaction('➡️')
		# 	await asyncio.sleep(0.3)
		# 	# await message.add_reaction('❌')
		# 	# await asyncio.sleep(1)
		if message.author.id != self.bot.user.id and message.channel.id == self.guild_forwarding[str(message.guild.id)]["pending"]:
			await message.add_reaction('✈️')
			# await message.add_reaction('❌')
			# await asyncio.sleep(0.3)

	
	@commands.Cog.listener()
	async def on_raw_reaction_add(self, reaction_payload):
		if self.bot.command_prefix != "=": return
		channel = await self.bot.fetch_channel(reaction_payload.channel_id)
		message = await channel.fetch_message(reaction_payload.message_id)
		emoji = str(reaction_payload.emoji)
		user = await self.bot.fetch_user(reaction_payload.user_id)
		if user.id == self.bot.user.id: return

		if emoji == "✈️":
			# logging.info("%s %s" % (self.guild_forwarding[str(message.guild.id)], self.is_twitter_message(message)))
			if message.author.id == self.bot.user.id and \
				self.is_twitter_message(message):
				# logging.info("Fowarding to img/vid/pending channels")
				new_message = None
				media_list = self.get_medias(message)
				forwarding_channels = self.guild_forwarding[str(message.guild.id)]
				for media, type in media_list:
					if type == "img" and forwarding_channels["img"]:
						new_message = await self.bot.get_channel(forwarding_channels["img"]).send(media)
					elif type == "vid" and forwarding_channels["vid"]:
						new_message = await self.bot.get_channel(forwarding_channels["vid"]).send(media)
					
					if not new_message: continue
					await new_message.add_reaction('❤️')
					await asyncio.sleep(0.3)
					await new_message.add_reaction('💩')
					await asyncio.sleep(0.3)
			elif message.channel.id == self.guild_forwarding[str(message.guild.id)]["pending"]:
				# logging.info("Fowarding to img/vid channels")
    
				new_message = None
				forwarding_channels = self.guild_forwarding[str(message.guild.id)]
				media = message.content
				if message.content:
					media = message.content
				elif message.attachments:
					media = message.attachments[0].url
				else: return
				logging.info("Pending media: %s" % media)
				if self.is_image_link(media.lower()) and forwarding_channels["img"]:
					new_message = await self.bot.get_channel(forwarding_channels["img"]).send(media)
				elif self.is_video_link(media.lower()) and forwarding_channels["vid"]:
					new_message = await self.bot.get_channel(forwarding_channels["vid"]).send(media)
				await message.delete()
				await asyncio.sleep(0.3)
				
				if not new_message: return
				await new_message.add_reaction('❤️')
				await asyncio.sleep(0.3)
				await new_message.add_reaction('💩')
				await asyncio.sleep(0.3)
					
		elif emoji == "➡️":
			# logging.info("%s %s" % (self.guild_forwarding[str(message.guild.id)], self.is_twitter_message(message)))
			if self.is_twitter_message(message):
				media_list = self.get_medias(message)
				forwarding_channels = self.guild_forwarding[str(message.guild.id)]
				for media, type in media_list:
					new_message = None
					if type == "img" and forwarding_channels["img"]:
						if forwarding_channels["pending"]:
							new_message = await self.bot.get_channel(forwarding_channels["pending"]).send(media)
						else:
							new_message = await self.bot.get_channel(forwarding_channels["img"]).send(media)
					elif type == "vid" and forwarding_channels["vid"]:
						if forwarding_channels["pending"]:
							new_message = await self.bot.get_channel(forwarding_channels["pending"]).send(media)
						else:
							new_message = await self.bot.get_channel(forwarding_channels["vid"]).send(media)
					await asyncio.sleep(0.3)
					
					if not new_message: continue
					if forwarding_channels["pending"]:
						await new_message.add_reaction('✈️')
						await asyncio.sleep(0.3)
					else:
						await new_message.add_reaction('❤️')
						await asyncio.sleep(0.3)
						await new_message.add_reaction('💩')
						await asyncio.sleep(0.3)
					# await new_message.add_reaction('❌')
					# await asyncio.sleep(0.3)
			
			else:			
				new_message = None
				media = message.content
				if message.content:
					media = message.content
				elif message.attachments:
					media = message.attachments[0].url
				else: return
				logging.info("Pending media: %s" % media)
				forwarding_channels = self.guild_forwarding[str(message.guild.id)]
				if self.is_image_link(media.lower()) and forwarding_channels["img"]:
					if forwarding_channels["pending"]:
						new_message = await self.bot.get_channel(forwarding_channels["pending"]).send(media)
					else:
						new_message = await self.bot.get_channel(forwarding_channels["img"]).send(media)
				elif self.is_video_link(media.lower()) and forwarding_channels["vid"]:
					if forwarding_channels["pending"]:
							new_message = await self.bot.get_channel(forwarding_channels["pending"]).send(media)
					else:
						new_message = await self.bot.get_channel(forwarding_channels["vid"]).send(media)
				await message.delete()
				await asyncio.sleep(0.3)
				
				if not new_message: return
				if forwarding_channels["pending"]:
					await new_message.add_reaction('✈️')
					await asyncio.sleep(0.3)
				else:
					await new_message.add_reaction('❤️')
					await asyncio.sleep(0.3)
					await new_message.add_reaction('💩')
					await asyncio.sleep(0.3)
						
		elif emoji == '❌':
			await message.delete()
			await asyncio.sleep(0.3)
						
	@commands.command(pass_context=True, help="bind as cache channel for forwarding")
	async def bindPendingChannelHere(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)
  
		if author.guild_permissions.administrator is not True: 
			await ctx.send("You don't have the permission.")
			return

		query_result = self.db["guild_info"].find_one({"guild_id": guild_id})
		
		if query_result:
			self.db["guild_info"].update_one(query_result, {"$set": {"forwarding_channels.pending": ctx.channel.id}})

		else:
			entry = copy.deepcopy(GUILD_TEMPLATE)
			entry["guild_id"] = guild_id
			entry["forwarding_channels"]["pending"] = ctx.channel.id
			self.db["guild_info"].insert_one(entry)
   
		self.guild_forwarding[guild_id]["pending"] = ctx.channel.id


	@commands.command(pass_context=True, help="bind as image channel for forwarding")
	async def bindImageChannelHere(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)
  
		if author.guild_permissions.administrator is not True: 
			await ctx.send("You don't have the permission.")
			return

		query_result = self.db["guild_info"].find_one({"guild_id": guild_id})
		
		if query_result:
			self.db["guild_info"].update_one(query_result, {"$set": {"forwarding_channels.img": ctx.channel.id}})

		else:
			entry = copy.deepcopy(GUILD_TEMPLATE)
			entry["guild_id"] = guild_id
			entry["forwarding_channels"]["img"] = ctx.channel.id
			self.db["guild_info"].insert_one(entry)
   
		self.guild_forwarding[guild_id]["img"] = ctx.channel.id


	@commands.command(pass_context=True, help="bind as video channel for forwarding")
	async def bindVideoChannelHere(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)
  
		if author.guild_permissions.administrator is not True: 
			await ctx.send("You don't have the permission.")
			return

		query_result = self.db["guild_info"].find_one({"guild_id": guild_id})
		
		if query_result:
			self.db["guild_info"].update_one(query_result, {"$set": {"forwarding_channels.vid": ctx.channel.id}})

		else:
			entry = copy.deepcopy(GUILD_TEMPLATE)
			entry["guild_id"] = guild_id
			entry["forwarding_channels"]["vid"] = ctx.channel.id
			self.db["guild_info"].insert_one(entry)

		self.guild_forwarding[guild_id]["vid"] = ctx.channel.id






	def update_database(self, user_id: str, guild_id: str, category: str, latest_id: int = 0, push_to_discord: bool = False, sync_to_telegram: bool = False, update_min: bool = False, update_max: bool = False, sub_category: str = None):
		query_result = self.query_twitter_info(user_id, guild_id, category)
		# logging.info(query_result)

		match category:
			case "timeline_info" | "self_like_info":
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
			case _:
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



	async def push_tweets(self, tweets: list[tweepy.models.Status], user_id: str, guild_id: str, category: str, sub_category: str, update_min: bool = False, update_max: bool = False, push_to_discord = False, sync_to_telegram: bool = False):

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
				tweet_ct += 1
				# logging.info("Pushing to discord channel...")
				# logging.info(media_list)
				message = await push_to_discord.send("||https://www.twitter.com/%s/status/%s||\n%s" % (tweet.user.screen_name, tweet.id, "\n".join([m[0][0] for m in media_list])))
				await asyncio.sleep(0.3)
				await message.add_reaction('✈️')
				await asyncio.sleep(0.3)
				await message.add_reaction('➡️')
				await asyncio.sleep(0.3)
				# await message.add_reaction('❌')
				# await asyncio.sleep(0.3)

			if sync_to_telegram:

				if self.sync_status[(user_id, guild_id)][category]:

					# logging.info("Sync to Telegram... %s" % tweet_link)
					# logging.info("Current_id: %d" % current_id)
					success = False
					# skipped = False
					while not success:
						# logging.info(media_list)
						try:
							await self.bot.get_cog("TelegramBot").send_medias(user_id, guild_id, media_list, "%s from @%s" % (tweet_link, screen_name), category)
							success = True
							tweet_ct += 1
							await asyncio.sleep(1)
						except aiogram.utils.exceptions.RetryAfter as err:

							logging.info("Finished %d tweets. Try again in %d seconds. Updating [%s-%s] info to database..."% (tweet_ct, err.timeout, category, sub_category))
							# logging.info("current_id %d on %s" % (current_id, "min" if update_min else "max"))
							if current_id:
								self.update_database(user_id, guild_id, category, current_id, push_to_discord, sync_to_telegram, update_min, update_max, sub_category)

							await asyncio.sleep(err.timeout)
						# except Exception as e:
						# 	logging.error(e)
						# except aiogram.utils.exceptions.BadRequest as err:
							# logging.error("Bad Request. Skipped.")
							# logging.error(err)
							# skpped = True
				
				
		logging.info("Finished %d tweets. Updating [%s-%s] info to database..." % (tweet_ct, category, sub_category))					
		# logging.info("current_id %d on %s" % (current_id, "min" if update_min else "max"))
		if current_id:
			self.update_database(user_id, guild_id, category, current_id, push_to_discord, sync_to_telegram, update_min, update_max, sub_category)



	async def get_tweets(self, user_id: str, guild_id: str, category: str, ctx: commands.Context = None, push_to_discord: bool = False, sync_to_telegram: bool = False, reverse: bool = False):
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
		MAX_DISCORD_COUNT, MAX_TELEGRAM_COUNT = 200, 200
		MAX_LIKE_QUERY_COUNT = 200

		if not (push_to_discord or sync_to_telegram): return




		logging.info("Fetching Twitter connection...")
		api = self.get_api(user_id, guild_id)
		if not api:
			# await ctx.send("Twitter connection failed, please reconnect your Twitter account.")
			return

		try:
			match category:
				case "timeline_info":
					logging.info("Acquiring timeline...")
					query_result = self.query_twitter_info(user_id, guild_id, category)

					update_max, update_min = False, False

					if push_to_discord:
						max_id = query_result[category]["max_id"]
						min_id = query_result[category]["min_id"]

					else:
						max_id = query_result[category]["max_sync_id"]
						min_id = query_result[category]["min_sync_id"]
					
					max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

					print(max_id, min_id)

					if reverse and min_id > 0:
						update_min = True
						tweets = list(tweepy.Cursor(api.home_timeline, max_id = min_id - 1, count= max_count, exclude_replies = True).items())
					elif (not reverse) and max_id > 0:
						update_max = True
						tweets = list(tweepy.Cursor(api.home_timeline, since_id = max_id, count= max_count, exclude_replies = True).items())
					else:
						update_max = True
						while True:
							try:
								tweets = list(tweepy.Cursor(api.home_timeline, count= max_count, exclude_replies = True).items())
								break
							except tweepy.errors.TooManyRequests:
								logging.info("Too Many Requests, wait 15 mins.")
								await asyncio.sleep(15*60)

						if len(tweets) > 0:
							if push_to_discord:
								query_result = self.query_twitter_info(user_id, guild_id, category)
								self.db["twitter_info"].update_one(query_result, {"$set": {
									"%s.max_id" % category: tweets[-1].id-1,
									"%s.min_id" % category: tweets[-1].id-1}})
							elif sync_to_telegram:
								query_result = self.query_twitter_info(user_id, guild_id, category)
								self.db["twitter_info"].update_one(query_result, {"$set": {
									"%s.max_sync_id" % category: tweets[-1].id-1,
									"%s.min_sync_id" % category: tweets[-1].id-1}})


					if len(tweets) == 0: 
						logging.info("Nothing fetched, continue.")
						exit()

					logging.info("Fetched %d tweets" % len(tweets))

					if not reverse: tweets = tweets[::-1]

					await self.push_tweets(tweets, user_id, guild_id, category, None, update_min, update_max, push_to_discord, sync_to_telegram)

				case "focus_info":
					query_result = self.query_twitter_info(user_id, guild_id, category)

					update_max, update_min = False, False
					# print(query_result[category])
					for user_name, sync_info in query_result[category].items():
						await asyncio.sleep(15)

						logging.info("Acquiring focused users %s..." % user_name)
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
							update_max = True
							tweets = list(tweepy.Cursor(api.user_timeline, screen_name = user_name, count= max_count, exclude_replies = True).items())

							if len(tweets) > 0:
								if push_to_discord:
									query_result = self.query_twitter_info(user_id, guild_id, category)
									self.db["twitter_info"].update_one(query_result, {"$set": {
										"%s.%s.min_id" % (category, user_name): tweets[-1].id-1,
										"%s.%s.max_id" % (category, user_name): tweets[-1].id-1}})
								elif sync_to_telegram:
									query_result = self.query_twitter_info(user_id, guild_id, category)
									self.db["twitter_info"].update_one(query_result, {"$set": {
										"%s.%s.min_sync_id" % (category, user_name): tweets[-1].id-1,
										"%s.%s.max_sync_id" % (category, user_name): tweets[-1].id-1}})

						if len(tweets) == 0: 
							logging.info("Nothing fetched, continue.")
							continue

						logging.info("Fetched %d tweets" % len(tweets))

						if not reverse: tweets = tweets[::-1]

						await self.push_tweets(tweets, user_id, guild_id, category, user_name, update_min, update_max, push_to_discord, sync_to_telegram)
			

				case "list_info":
					query_result = self.query_twitter_info(user_id, guild_id, category)

					update_max, update_min = False, False
					# print(query_result[category])
					for list_id, sync_info in query_result[category].items():
						await asyncio.sleep(15)
						logging.info("Acquiring list statuses %s..." % list_id)
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
							update_max = True
							tweets = list(tweepy.Cursor(api.list_timeline, list_id = list_id, count= max_count).items())

							if len(tweets) > 0:
								if push_to_discord:
									query_result = self.query_twitter_info(user_id, guild_id, category)
									self.db["twitter_info"].update_one(query_result, {"$set": {
										"%s.%s.min_id" % (category, list_id): tweets[-1].id-1,
										"%s.%s.max_id" % (category, list_id): tweets[-1].id-1}})
								elif sync_to_telegram:
									query_result = self.query_twitter_info(user_id, guild_id, category)
									self.db["twitter_info"].update_one(query_result, {"$set": {
										"%s.%s.min_sync_id" % (category, list_id): tweets[-1].id-1,
										"%s.%s.max_sync_id" % (category, list_id): tweets[-1].id-1}})

						if len(tweets) == 0: 
							logging.info("Nothing fetched, continue.")
							continue

						logging.info("Fetched %d tweets" % len(tweets))

						if not reverse: tweets = tweets[::-1]

						await self.push_tweets(tweets, user_id, guild_id, category, list_id, update_min, update_max, push_to_discord, sync_to_telegram)
			
				case "like_info":
					query_result = self.query_twitter_info(user_id, guild_id, category)

					update_max, update_min = False, False
					# print(query_result[category])
					for user_name, sync_info in query_result[category].items():
						await asyncio.sleep(15)	
						logging.info("Acquiring like statuses %s..." % user_name)
						if push_to_discord:
							max_id, min_id = sync_info["max_id"], sync_info["min_id"]

						elif sync_to_telegram:
							max_id, min_id = sync_info["max_sync_id"], sync_info["min_sync_id"]
						
						max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

						# if reverse and min_id > 0:
						# 	update_min = True
						# 	tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, count= max_count).items())
						if (not reverse) and max_id > 0:
							update_max = True
							tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, count= max_count).items(MAX_LIKE_QUERY_COUNT))
							id_list = [tweet.id for tweet in tweets]
							if max_id in id_list:
								tweets = tweets[:id_list.index(max_id)]
							# else:
							# 	tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, count= max_count).items())
							# 	id_list = [tweet.id for tweet in tweets]
							# 	if max_id in id_list:
							# 		tweets = tweets[:id_list.index(max_id)]
						else:
							update_max = True
							tweets = list(tweepy.Cursor(api.get_favorites, screen_name = user_name, count= max_count).items())

							if len(tweets) > 0:
								if push_to_discord:
									query_result = self.query_twitter_info(user_id, guild_id, category)
									self.db["twitter_info"].update_one(query_result, {"$set": {
										"%s.%s.min_id" % (category, user_name): tweets[-1].id}})
								elif sync_to_telegram:
									query_result = self.query_twitter_info(user_id, guild_id, category)
									self.db["twitter_info"].update_one(query_result, {"$set": {
										"%s.%s.min_sync_id" % (category, user_name): tweets[-1].id}})

						if len(tweets) == 0: 
							logging.info("Nothing fetched, continue.")
							continue

						logging.info("Fetched %d tweets" % len(tweets))

						tweets = tweets[::-1]

						await self.push_tweets(tweets, user_id, guild_id, category, user_name, update_min, update_max, push_to_discord, sync_to_telegram)
			
				case "self_like_info":
					logging.info("Acquiring selflike statuses...")
					query_result = self.query_twitter_info(user_id, guild_id, category)

					update_max, update_min = False, False
					sync_info = query_result[category]

					if push_to_discord:
						max_id, min_id = sync_info["max_id"], sync_info["min_id"]

					elif sync_to_telegram:
						max_id, min_id = sync_info["max_sync_id"], sync_info["min_sync_id"]
					
					max_count = MAX_DISCORD_COUNT if push_to_discord else MAX_TELEGRAM_COUNT

					# if reverse and min_id > 0:
					# 	update_min = True
					# 	tweets = list(tweepy.Cursor(api.get_favorites, count= max_count).items(MAX_LIKE_QUERY_COUNT))
					if (not reverse) and max_id > 0:
						update_max = True
						tweets = list(tweepy.Cursor(api.get_favorites, count= max_count).items(MAX_LIKE_QUERY_COUNT))
						id_list = [tweet.id for tweet in tweets]
						if max_id in id_list:
							tweets = tweets[:id_list.index(max_id)]
						else:
							tweets = list(tweepy.Cursor(api.get_favorites, count= max_count).items())
							id_list = [tweet.id for tweet in tweets]
							if max_id in id_list:
								tweets = tweets[:id_list.index(max_id)]
					else:
						update_max = True
						tweets = list(tweepy.Cursor(api.get_favorites, count= max_count).items())

						if len(tweets) > 0:
							if push_to_discord:
								query_result = self.query_twitter_info(user_id, guild_id, category)
								self.db["twitter_info"].update_one(query_result, {"$set": {
									"%s.min_id" % category: tweets[-1].id}})
							elif sync_to_telegram:
								query_result = self.query_twitter_info(user_id, guild_id, category)
								self.db["twitter_info"].update_one(query_result, {"$set": {
									"%s.min_sync_id" % category: tweets[-1].id}})

					if len(tweets) == 0: 
						logging.info("Nothing fetched, continue.")
						return

					logging.info("Fetched %d tweets" % len(tweets))
					# print(tweets[0].id)
					tweets = tweets[::-1]

					await self.push_tweets(tweets, user_id, guild_id, category, None, update_min, update_max, push_to_discord, sync_to_telegram)
		except tweepy.errors.TooManyRequests:
			logging.info("Too Many Requests")

		
				


	async def removeEntry(self, ctx: commands.Context, sync_type: str, arg: str):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		logging.info("Adding to %s tracking..." % sync_type)

		match sync_type:
			case "like_info":
				re_result = self.user_link_pattern.search(arg)
			case "list_info":
				re_result = self.list_link_pattern.search(arg)
			case "focus_info":
				re_result = self.user_link_pattern.search(arg)

		if not re_result:
			await ctx.send("Please provide a valid link.")
			return

		keyword = re_result[2]

		await self.remove_by_link(user_id, guild_id, sync_type, keyword)
		
  
  
  
	async def remove_by_link(self, user_id: str, guild_id: str, type_name: str, keyword: str):
		"""
		Add binding info into the database

		:param user_id: id of the user
		:param guild_id: id of the guild
		:param type_name: type of the info to add, from {"list_info", "focus_info", "like_info"}
		:param keyword: list or user's screen name
		:return: None
		"""
		query_result = self.query_twitter_info(user_id, guild_id, type_name)

		finished = False
		if query_result and type_name in query_result.keys():
			if keyword in query_result[type_name].keys():
				return
			
			self.db["twitter_info"].update_one(query_result, {"$unset": {"%s.%s" % (type_name, keyword): 1}})



	@commands.command(pass_context=True, help="add an account for focus tracking")
	async def removeFocus(self, ctx: commands.Context, *, arg: str):
		
		await self.removeEntry(ctx, "focus_info", arg)



	@commands.command(pass_context=True, help="add an account for list tracking")
	async def removeList(self, ctx: commands.Context, *, arg: str):
		
		await self.removeEntry(ctx, "list_info", arg)



	@commands.command(pass_context=True, help="add an account for like tracking")
	async def removeLike(self, ctx: commands.Context, *, arg: str):
		
		await self.removeEntry(ctx, "like_info", arg)



	async def add_by_link(self, user_id: str, guild_id: str, type_name: str, keyword: str):
		"""
		Add binding info into the database

		:param user_id: id of the user
		:param guild_id: id of the guild
		:param type_name: type of the info to add, from {"list_info", "focus_info", "like_info"}
		:param keyword: list or user's screen name
		:return: None
		"""
		query_result = self.query_twitter_info(user_id, guild_id, type_name)

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
	async def addFocus(self, ctx: commands.Context, *, arg: str):
		
		await self.addEntry(ctx, "focus_info", arg)



	@commands.command(pass_context=True, help="add an account for list tracking")
	async def addList(self, ctx: commands.Context, *, arg: str):
		
		await self.addEntry(ctx, "list_info", arg)



	@commands.command(pass_context=True, help="add an account for like tracking")
	async def addLike(self, ctx: commands.Context, *, arg: str):
		
		await self.addEntry(ctx, "like_info", arg)


	async def addEntry(self, ctx: commands.Context, sync_type: str, arg: str):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		logging.info("Adding to %s tracking..." % sync_type)

		match sync_type:
			case "like_info":
				re_result = self.user_link_pattern.search(arg)
			case "list_info":
				re_result = self.list_link_pattern.search(arg)
			case "focus_info":
				re_result = self.user_link_pattern.search(arg)

		if not re_result:
			await ctx.send("Please provide a valid link.")
			return

		keyword = re_result[2]

		await self.add_by_link(user_id, guild_id, sync_type, keyword)


	async def get_tweets_once(self, ctx: commands.Context, sync_type: str):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		await self.get_tweets(user_id, guild_id, sync_type, ctx, push_to_discord= ctx)

	@commands.command(pass_context=True, help="grab medias from your Twitter timeline")
	async def getTimeline(self, ctx: commands.Context):

		await self.get_tweets_once(ctx, "timeline_info")

	@commands.command(pass_context=True, help="grab medias from your Twitter focused users")
	async def getFocus(self, ctx: commands.Context):
		
		await self.get_tweets_once(ctx, "focus_info")


	@commands.command(pass_context=True, help="grab medias from your Twitter lists")
	async def getList(self, ctx: commands.Context):
		
		await self.get_tweets_once(ctx, "list_info")

		

	@commands.command(pass_context=True, help="grab medias from likes from target users")
	async def getLike(self, ctx: commands.Context):
		
		await self.get_tweets_once(ctx, "like_info")

	@commands.command(pass_context=True, help="grab medias from own likes")
	async def getMyLike(self, ctx: commands.Context):
		
		await self.get_tweets_once(ctx, "self_like_info")




	@commands.command(pass_context=True, help="grab medias from your Twitter timeline (older than recorded)")
	async def timelineReverse(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		await self.get_tweets(user_id, guild_id, "timeline_info", ctx, push_to_discord= True, reverse = True)


	@commands.command(pass_context=True, help="sync all elements according to bit patterns (to telegram): tl-focus-like-list-selflike. E.g., 11001 means sync tl+focus+selflike ")
	async def syncAll(self, ctx: commands.Context, *, arg: str):
		try:
			value = int(arg, 2)
			if value <= 0 or value >= 2**5: raise ValueError
		except:
			return await ctx.send("Invalid argument.")
		
		sync_ctgs = [ctg for i, ctg in enumerate(self.CATEGORIES) if value & 1 << i]
		for ctg in sync_ctgs:
			await self.enable_sync(ctx, ctg, "telegram")

			
	@commands.command(pass_context=True, help="sync all elements according to bit patterns (to discord channel): tl-focus-like-list-selflike. E.g., 11001 means sync tl+focus+selflike ")
	async def syncAllHere(self, ctx: commands.Context, *, arg: str):
		try:
			value = int(arg, 2)
			if value <= 0 or value >= 2**5: raise ValueError
		except:
			return await ctx.send("Invalid argument.")
		
		sync_ctgs = [ctg for i, ctg in enumerate(self.CATEGORIES) if value & 1 << i]
		asyncio.gather(*[self.enable_sync(ctx, ctg, "discord") for ctg in sync_ctgs])
		if sync_ctgs and (not self.sync.is_running()):
			self.sync.start()

		


		

	async def enable_sync(self, ctx: commands.Context, sync_type: str, target: str, target_channel: str = ""):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if target == "telegram":
			if not self.bot.get_cog("TelegramBot").get_telegram_channel(user_id, guild_id, target_channel):
				await ctx.send("Please bind your Telegram channel first.")
				return

		logging.info("Toggle %s %s sync for %s" % (target, sync_type, author))
		if target == "telegram":
			self.sync_status[(user_id, guild_id)][sync_type][target] = True
		else:
			self.sync_status[(user_id, guild_id)][sync_type][target] = ctx


	@commands.command(pass_context=True)
	async def syncLikeHere(self, ctx: commands.Context):

		await self.enable_sync(ctx, "like_info", "discord")



	@commands.command(pass_context=True)
	async def syncFocusHere(self, ctx: commands.Context):

		await self.enable_sync(ctx, "focus_info", "discord")
		


	@commands.command(pass_context=True)
	async def syncListHere(self, ctx: commands.Context):

		await self.enable_sync(ctx, "list_info", "discord")



	@commands.command(pass_context=True)
	async def syncTimelineHere(self, ctx: commands.Context):

		await self.enable_sync(ctx, "timeline_info", "discord")

	@commands.command(pass_context=True)
	async def syncMyLikeHere(self, ctx: commands.Context):

		await self.enable_sync(ctx, "self_like_info", "discord")



	@commands.command(pass_context=True)
	async def syncLike(self, ctx: commands.Context):

		await self.enable_sync(ctx, "like_info", "telegram", "like_channel")



	@commands.command(pass_context=True)
	async def syncFocus(self, ctx: commands.Context):

		await self.enable_sync(ctx, "focus_info", "telegram", "focus_channel")


	@commands.command(pass_context=True)
	async def syncList(self, ctx: commands.Context):

		await self.enable_sync(ctx, "list_info", "telegram", "list_channel")



	@commands.command(pass_context=True)
	async def syncTimeline(self, ctx: commands.Context):

		await self.enable_sync(ctx, "timeline_info", "telegram", "tl_channel")

	@commands.command(pass_context=True)
	async def syncMyLike(self, ctx: commands.Context):

		await self.enable_sync(ctx, "self_like_info", "telegram", "self_like_channel")


	@commands.command(pass_context=True)
	async def syncTimelineReverse(self, ctx: commands.Context):
		author, guild = ctx.message.author, ctx.guild
		user_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").get_telegram_channel(user_id, guild_id, "tl_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Retrieving older tweets in timeline...")
		await self.get_tweets(user_id, guild_id, "timeline_info", None, sync_to_telegram= True, reverse = True)