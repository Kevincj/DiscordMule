#!/usr/bin/python3

import re
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
from template import TWEET_TEMPLATE, USER_TEMPLATE





class Twitter(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db

		self.apis = defaultdict(lambda: None)

		self.binding_auths = defaultdict(lambda: None)
		self.bounded_auths = defaultdict(lambda: None)

		self.sync_tl_context = defaultdict(lambda: None)
		self.sync_likes_context = defaultdict(lambda: None)
		self.sync_lists_context = defaultdict(lambda: None)

		self.url_pattern = re.compile("(https?:..t.co.\w+)$")


		self.RATE_LIMIT_TL = 15

	@commands.command(pass_context=True, help="request a Twitter connection")
	async def connectTwitter(self, ctx: commands.Context):

		author = ctx.message.author

		query_result = self.db["user_info"].find_one({"user_id": str(author.id), "guild_id": str(ctx.guild.id)})
		if query_result:
			self.db["user_info"].update_one(query_result, {"$set": {"tweet_token": None}})

		auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])

		await ctx.send("Please authorize via the following link: %s\n\
			And use \"=bindTwitter your_verifier\" to bind your Twitter account." % auth.get_authorization_url())
		self.binding_auths[author.id] = auth



	@commands.command(pass_context=True, help="bind Twitter account")
	async def bindTwitter(self, ctx: commands.Context, *, arg: str):
		
		author = ctx.message.author

		if not self.binding_auths[author.id]:
			await ctx.send("Please use \"=connectTwitter\" first to request a token before binding.")
			return

		query_result = self.db["user_info"].find_one({"user_id": str(author.id), "guild_id": str(ctx.guild.id)})
		access_token, access_secret = self.binding_auths[author.id].get_access_token(arg)
		if not (access_token and access_secret):
			await ctx.send("Invalid verifier, please try again.")
			return

		if query_result:
			self.db["user_info"].update_one(query_result, {"$set": {
					"tweet_token": {
						"access_token": access_token,
						"access_secret": access_secret
					}
				}})
		else:
			self.db["user_info"].insert_one({
					"user_id": str(author.id),
					"guild_id": str(ctx.guild.id),
					"tweet_token": {
						"access_token": access_token,
						"access_secret": access_secret
					}
				})

		self.binding_auths[author.id].set_access_token(access_token, access_secret)
		self.bounded_auths[author.id] = tweepy.API(self.binding_auths[author.id])
		self.binding_auths[author.id] = None

		await ctx.send("Successfully bounded to your Twitter account.")





	def getAPI(self, author_id, guild_id):
		if not self.apis[(author_id, guild_id)]:

			query_result = self.db["user_info"].find_one({"user_id": author_id, "guild_id": guild_id})
			# logging.info("Query result:", query_result["tweet_token"]["access_token"],query_result["tweet_token"]["access_secret"])
			
			if query_result:
				
				logging.info("Setting up Twitter connection...")
				auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])
				auth.set_access_token(query_result["tweet_token"]["access_token"], query_result["tweet_token"]["access_secret"])
				api = tweepy.API(auth)

		else:
			api = self.apis[(author_id, guild_id)]
			
		if api:
			self.apis[(author_id, guild_id)] = api

		return api




	# def getMembersFromList(self, list_id: str):



	async def getTimeline(self, ctx: commands.Context, push_to_discord = False, sync_to_telegram = False, reverse = False):

		if not (push_to_discord or sync_to_telegram): return

		author, guild = ctx.message.author, ctx.guild
		author_id, guild_id = str(author.id), str(guild.id)

		logging.info("Fetching Twitter connection...")
		api = self.getAPI(author_id, guild_id)
		if not api:
			await ctx.send("Twitter connection failed, please reconnect your Twitter account.")
			return

		last_id, first_id = None, None
		logging.info("Acquiring timeline...")
		query_result = self.db["user_info"].find_one({"user_id": author_id, "guild_id": guild_id})
		if push_to_discord:
			last_id = query_result["max_timeline_id"]
			first_id = query_result["min_timeline_id"]-1

		else:
			last_id = query_result["max_sync_timeline_id"]
			first_id = query_result["min_sync_timeline_id"]-1
		

		for query_count in range(self.RATE_LIMIT_TL - 1):

			if reverse:
				if first_id > 0:
					tweets = api.home_timeline(max_id = first_id, count= 200, exclude_replies = True)
				else:
					tweets = api.home_timeline(count= 200, exclude_replies = True)
			else:
				if last_id > 0:
					tweets = api.home_timeline(since_id = last_id, count= 200, exclude_replies = True)
				else:
					tweets = api.home_timeline(count= 200, exclude_replies = True)


			if len(tweets) == 0: break
			logging.info("Got %d tweets" % len(tweets))

			first_id = tweets[0].id

			for tweet in tweets:

				re_result = self.url_pattern.search(tweet.text)
				if not re_result:
					continue
				
				tweet_link = re_result[1]
				screen_name = tweet.user.screen_name
				media_lists = []

				last_id = tweet.id
				if hasattr(tweet, "extended_entities"):
					extended_entities = tweet.extended_entities
					if "media" in extended_entities.keys():
						media_list = []
						for media in extended_entities["media"]:
							if media["type"] == "video":
								video_vars = media["video_info"]["variants"]
								best_bitrate = None
								url = None
								for var in video_vars:
									if var["content_type"] == "video/mp4":
										if (not best_bitrate) or best_bitrate < var["bitrate"]:
											url = var["url"]
											best_bitrate = var["bitrate"]
								media_list.append((url, True))
							elif media["type"] == "photo":
								url = media["media_url"]
								media_list.append((url, False))
						if media_list:
							media_lists.append(media_list)

				if len(media_lists) == 0: continue

				if push_to_discord:
					logging.info("Pushing to discord channel...")
					for media in media_lists:
						await ctx.send(media[0][0])

				if sync_to_telegram:

					if self.sync_tl_context[(author_id, guild_id)]:

						logging.info("Sync to Telegram... %s" % tweet_link)

						success = False
						# skipped = False
						while not success:
							# logging.info(media_lists)
							try:
								await self.bot.get_cog("TelegramBot").sendMedias(ctx, media_lists, "%s from @%s" % (tweet_link, screen_name), "timeline")
								success = True
								await asyncio.sleep(1)
							except aiogram.utils.exceptions.RetryAfter as err:
								logging.error("Try again in %d seconds" % err.timeout)
								await asyncio.sleep(err.timeout)
							# except aiogram.utils.exceptions.BadRequest as err:
								# logging.error("Bad Request. Skipped.")
								# logging.error(err)
								# skpped = True


					
			logging.info("Updating timeline info to database...")
			if reverse:
				if push_to_discord:
					self.db["user_info"].update_one(query_result, {"$set": {"min_timeline_id": first_id}})
				if sync_to_telegram:
					self.db["user_info"].update_one(query_result, {"$set": {"min_sync_timeline_id": first_id}})
			else:
				if push_to_discord:
					self.db["user_info"].update_one(query_result, {"$set": {"max_timeline_id": last_id}})
				if sync_to_telegram:
					self.db["user_info"].update_one(query_result, {"$set": {"max_sync_timeline_id": last_id}})




	@commands.command(pass_context=True, help="grab medias from your Twitter timeline")
	async def timeline(self, ctx: commands.Context):

		await self.getTimeline(ctx, push_to_discord= True)



	@tasks.loop(minutes=60)
	async def sync(self):

		logging.info("Sync...")
		for key, ctx in self.sync_tl_context.items():

			if ctx:
				await self.getTimeline(ctx, sync_to_telegram= True)

		logging.info("Finished sync.")



	@commands.command(pass_context=True)
	async def syncLikes(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		author_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(ctx, "like_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_likes_context[(author_id, guild_id)] = ctx

		if not self.sync.is_running():
			self.sync.start()



	@commands.command(pass_context=True)
	async def syncLists(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		author_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(ctx, "list_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_lists_context[(author_id, guild_id)] = ctx

		if not self.sync.is_running():
			self.sync.start()



	@commands.command(pass_context=True)
	async def syncTimeline(self, ctx: commands.Context):

		author, guild = ctx.message.author, ctx.guild
		author_id, guild_id = str(author.id), str(guild.id)

		if not self.bot.get_cog("TelegramBot").getTelegramChannel(ctx, "tl_channel"):
			await ctx.send("Please bind your Telegram channel first.")
			return

		logging.info("Toggle tl sync for %d" % author.id)
		self.sync_tl_context[(author_id, guild_id)] = ctx

		if not self.sync.is_running():
			self.sync.start()


	@commands.command
	async def sayHiFromTwitterCog(self, ctx: commands.Context):
		await self.bot.get_cog("General").hi(ctx)
