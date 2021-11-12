#!/usr/bin/python3


import discord
import logging
import pymongo
import configparser
from discord.ext import commands
from telegram.ext import Updater
from collections import defaultdict
from telegram.ext import CommandHandler
from template import TWEET_TEMPLATE, USER_TEMPLATE

class TelegramBot(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db

		self.updater = Updater(token=self.config['Telegram']['token'], use_context=True)
		self.dispatcher = self.updater.dispatcher
		self.commands = {}


	@commands.command(pass_context=True, help="activate telegram bot")
	async def activateTelegram(self, ctx: commands.Context):

		logging.info("Activating Telegram bot...")
		for cmd, handler in self.commands.items():
			self.dispatcher.add_handler(CommandHandler(cmd, handler))
		self.updater.start_polling()

