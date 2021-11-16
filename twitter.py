#!/usr/bin/python3

import re
import tweepy
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

		self.api = None
		self.binding_auths = defaultdict(lambda: None)
		self.bounded_auths = defaultdict(lambda: None)
		self.syncStatus = defaultdict(lambda: False)

		self.syncContext = defaultdict(lambda: None)

		self.url_pattern = re.compile("(https?:..t.co.\w+)$")



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



	async def getTimeline(self, ctx: commands.Context, push_to_discord = False, sync_to_telegram = False):
		author = ctx.message.author

		api = None

		query_result = self.db["user_info"].find_one({"user_id": str(author.id), "guild_id": str(ctx.guild.id)})
		# logging.info("Query result:", query_result["tweet_token"]["access_token"],query_result["tweet_token"]["access_secret"])
		
		if query_result:
			
			logging.info("Setting up Twitter connection...")
			auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])
			auth.set_access_token(query_result["tweet_token"]["access_token"], query_result["tweet_token"]["access_secret"])
			api = tweepy.API(auth)
			
		if not api:
			await ctx.send("Twitter connection failed, please reconnect your Twitter account.")
			return

		logging.info("Acquiring timeline...")
		if push_to_discord:
			last_id = query_result["timeline_id"]
		else:
			last_id = query_result["sync_timeline_id"]
		tweets = api.home_timeline(since_id = last_id)

		for tweet in tweets:

			re_result = self.url_pattern.search(tweet.text)
			if not re_result:
				continue
			
			tweet_link = re_result[1]
			media_list = []

			last_id = tweet.id_str
			if hasattr(tweet, "extended_entities"):
				extended_entities = tweet.extended_entities
				if "media" in extended_entities.keys():
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

			if push_to_discord:
				for media in media_list:
					await ctx.send(media[0])

			if sync_to_telegram:
				if self.syncStatus[(str(author.id), str(ctx.guild.id))]:
					logging.info("Sync to Telegram...")


					await self.bot.get_cog("TelegramBot").sendMedias(ctx, media_list, tweet_link)

		logging.info("Updating timeline info to database...%s" % last_id)
		if push_to_discord:
			self.db["user_info"].update_one(query_result, {"$set": {"timeline_id": last_id}})
		else:
			self.db["user_info"].update_one(query_result, {"$set": {"sync_timeline_id": last_id}})

	@commands.command(pass_context=True, help="grab medias from your Twitter timeline")
	async def timeline(self, ctx: commands.Context):

		await self.getTimeline(ctx, push_to_discord= True, sync_to_telegram= True)



	@tasks.loop(minutes=15.0)
	async def sync(self):

		for key, value in self.syncStatus.items():
			if value:
				await self.getTimeline(self.syncContext[key], sync_to_telegram= True)




	@commands.command(pass_context=True)
	async def syncToTelegram(self, ctx: commands.Context):

		author = ctx.message.author

		if not self.bot.get_cog("TelegramBot").checkBindingStatus(ctx):
			await ctx.send("Please bind your Telegram channel first.")
			return

		self.syncStatus[(str(author.id), str(ctx.guild.id))] = True

		self.syncContext[(str(author.id), str(ctx.guild.id))] = ctx



	@commands.command
	async def sayHiFromTwitterCog(self, ctx: commands.Context):
		await self.bot.get_cog("General").hi(ctx)
