#!/usr/bin/python3

import tweepy
import discord
import logging
import configparser
from discord.ext import commands


class Twitter(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser):
		self.bot = bot
		self.config = config
		self.api = None

		self.loadTwitter()


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

