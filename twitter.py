#!/usr/bin/python3


import tweepy
import discord
import logging
import pymongo
import configparser
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




	@commands.command(pass_context=True, help="grab medias from your Twitter timeline")
	async def timeline(self, ctx: commands.Context):

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
		last_id = query_result["timeline_id"]
		tweets = api.home_timeline(since_id = last_id)

		for tweet in tweets:
			last_id = tweet.id_str
			if hasattr(tweet, "extended_entities"):
				extended_entities = tweet.extended_entities
				if "media" in extended_entities.keys():
					medias = extended_entities["media"]
					for media in medias:
						if media["type"] == "video":
							video_vars = media["video_info"]["variants"]
							best_bitrate = None
							url = None
							for var in video_vars:
								if var["content_type"] == "video/mp4":
									if (not best_bitrate) or best_bitrate < var["bitrate"]:
										url = var["url"]
										best_bitrate = var["bitrate"]
							await ctx.send(url)
						elif media["type"] == "photo":
							url = media["media_url"]
							await ctx.send(url)

		logging.info("Updating timeline info to database...%s" % last_id)
		self.db["user_info"].update_one(query_result, {"$set": {"timeline_id": last_id}
			})


	@commands.command(pass_context=True)
	async def sayHiFromTwitterCog(self, ctx: commands.Context):
		await self.bot.get_cog("General").hi(ctx)

	# def loadTwitter(self) -> None:

	# 	logging.info("Setting up Twitter access...")
	# 	if "AccessToken" in self.config["Twitter"]:
	# 		auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])
	# 		auth.set_access_token(self.config["Twitter"]["AccessToken"], self.config["Twitter"]["AccessSecret"])
	# 		self.api = tweepy.API(auth)

	# 	if not self.api:
	# 		logging.info("Fetching access token and secret...")

	# 		try:
	# 			auth = tweepy.OAuthHandler(self.config["Twitter"]["APIKey"], self.config["Twitter"]["APISecret"])
	# 			redirect_url = auth.get_authorization_url()

	# 			logging.info("Link: %s" % redirect_url)
	# 			verifier = input("PIN: ")

	# 			self.config["Twitter"]["AccessToken"], self.config["Twitter"]["AccessSecret"] = \
	# 									auth.get_access_token(verifier)
	# 			logging.info("Received access token: %s" %  self.config["Twitter"]["AccessToken"])
	# 			logging.info("Received access token: %s" %  self.config["Twitter"]["AccessSecret"])
	# 			auth.set_access_token(self.config["Twitter"]["AccessToken"], self.config["Twitter"]["AccessSecret"])

	# 			saveConfig(config_file)
	# 			self.api = tweepy.API(auth)

	# 		except tweepy.TweepyException as error:
	# 			logging.info("Error!")

	# 	if self.api:
	# 		logging.info("Connected to Twitter successfullly.")
	# 	else:
	# 		logging.error("Failed to connect to Twitter.")

