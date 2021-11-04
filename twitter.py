#!/usr/bin/python3

import tweepy
import discord
import logging
import pymongo
import configparser
from collections import defaultdict
from discord.ext import commands


class Twitter(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser):
		self.bot = bot
		self.config = config
		self.api = None
		self.binding_auths = defaultdict(lambda: None)
		self.bounded_auths = defaultdict(lambda: None)
		self.loadTwitter()
		self.loadDB()



	def loadDB(self):


		logging.info("Connecting to MongoDB...")
		dbclient = pymongo.MongoClient("mongodb://localhost:27017/")

		# Create the database / locate the database
		self.db = dbclient["discord_mule"]

		existing_col = self.db.list_collection_names()

		guild_info = self.db["guild_info"]	
		if "guild_info" not in existing_col:
			guild_info.insert_one({
				"guild_id": None,
				"roles": [],
				"reactable_channels": [],
				"forwarding_channels": {
					"img": None,
					"vid": None
					}
				})

		media_info = self.db["media_info"]
		if "media_info" not in existing_col:
			media_info.insert_one({
				"media_url": None,
				"tweet_id": None
				})


		tweet_info = self.db["tweet_info"]
		if "tweet_info" not in existing_col:
			tweet_info.insert_one({
				"tweet_id": None,
				"media_urls": [],
				"author_id": None,
				"liked": False,
				"likes": 0,
				"retweets": 0,
				})

		user_info = self.db["user_info"]
		if "user_info" not in existing_col:
			user_info.insert_one({
				"user_id": None,
				"guild_id": None,
				"tweet_token": None
				})

	@commands.command(pass_context=True, help="request a Twitter connection")
	async def connectTwitter(self, ctx: commands.Context):

		author = ctx.message.author

		query_result = self.db["user_info"].find_one({"user_id": author.id, "guild_id": ctx.guild.id})
		if query_result:
			self.db["user_info"].update_one(query_result[0], {"$set": {"tweet_token": None}})

		auth = tweepy.OAuthHandler(self.config['Twitter']['APIKey'], self.config['Twitter']['APISecret'])

		await ctx.send("Please authorize via the following link: %s\n\
			And use \"=bind your_verifier\" to bind your Twitter account." % auth.get_authorization_url())
		self.binding_auths[author.id] = auth

	@commands.command(pass_context=True, help="bind Twitter account")
	async def bindTwitter(self, ctx: commands.Context, *, arg: str):
		
		author = ctx.message.author

		if not self.binding_auths[author.id]:
			await ctx.send("Please use \"=connectTwitter\" first to request a token before binding.")
			return

		query_result = self.db["user_info"].find_one({"user_id": author.id, "guild_id": ctx.guild.id})
		access_token, access_secret = self.binding_auths[author.id].get_access_token(arg)
		if not (access_token and access_secret):
			await ctx.send("Invalid verifier, please try again.")
			return

		if query_result:
			self.db["user_info"].update_one(query_result[0], {"$set": {
					"tweet_token": {
						"access_token": access_token,
						"access_secret": access_secret
					}
				}})
		else:
			self.db["user_info"].insert_one({
					"user_id": author.id,
					"guild_id": ctx.guild.id,
					"tweet_token": {
						"access_token": access_token,
						"access_secret": access_secret
					}
				})

		self.binding_auths[author.id].set_access_token(access_token, access_secret)
		self.bounded_auths[author.id] = tweepy.API(self.binding_auths[author.id])
		self.binding_auths[author.id] = None

		await ctx.send("Successfully bounded to your Twitter account.")


	def loadTwitter(self) -> None:

		logging.info("Setting up Twitter access...")
		if 'AccessToken' in self.config['Twitter']:
			auth = tweepy.OAuthHandler(self.config['Twitter']['APIKey'], self.config['Twitter']['APISecret'])
			auth.set_access_token(self.config['Twitter']['AccessToken'], self.config['Twitter']['AccessSecret'])
			self.api = tweepy.API(auth)

		if not self.api:
			logging.info("Fetching access token and secret...")

			try:
				auth = tweepy.OAuthHandler(self.config['Twitter']['APIKey'], self.config['Twitter']['APISecret'])
				redirect_url = auth.get_authorization_url()

				logging.info("Link: %s" % redirect_url)
				verifier = input('PIN: ')

				self.config['Twitter']['AccessToken'], self.config['Twitter']['AccessSecret'] = \
										auth.get_access_token(verifier)
				logging.info("Received access token: %s" %  self.config['Twitter']['AccessToken'])
				logging.info("Received access token: %s" %  self.config['Twitter']['AccessSecret'])
				auth.set_access_token(self.config['Twitter']['AccessToken'], self.config['Twitter']['AccessSecret'])

				saveConfig(config_file)
				self.api = tweepy.API(auth)

			except tweepy.TweepyException as error:
				logging.info('Error!')

		if self.api:
			logging.info("Connected to Twitter successfullly.")
		else:
			logging.error("Failed to connect to Twitter.")

