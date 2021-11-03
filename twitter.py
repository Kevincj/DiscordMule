#!/usr/bin/python3

import tweepy
import discord
import logging
import pymongo
import configparser
from discord.ext import commands


class Twitter(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser):
		self.bot = bot
		self.config = config
		self.api = None

		self.loadTwitter()
		self.loadDB()



	def loadDB(self):


		logging.info("Connecting to MongoDB...")
		dbclient = pymongo.MongoClient("mongodb://localhost:27017/")

		dblist = dbclient.list_database_names()
		if "discord_mule" not in dblist:
			self.db = dbclient["discord_mule"]
		else:
			self.db = dbclient["discord_mule"]

		existing_col = self.db.list_collection_names()
		if "guild_info" not in existing_col:
			guild_info = self.db["guild_info"]
			guild_info.insert_one({
				"guild_id": None,
				"roles": [],
				"reactable_channels": [],
				"forwarding_channels": {
					"img": None,
					"vid": None
					}
				})

		if "media_info" not in existing_col:
			media_info = self.db["media_info"]
			media_info.insert_one({
				"media_url": None,
				"tweet_id": None
				})

		if "tweet_info" not in existing_col:
			tweet_info = self.db["tweet_info"]
			tweet_info.insert_one({
				"tweet_id": None,
				"media_urls": [],
				"author_id": None,
				"liked": False,
				"likes": 0,
				"retweets": 0,
				})

		if "user_info" not in existing_col:
			user_info = self.db["user_info"]
			user_info.insert_one({
				"user_id": None,
				"guild_id": None,
				"tweet_token": None
				})


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

