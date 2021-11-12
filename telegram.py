#!/usr/bin/python3


import discord
import logging
import pymongo
from collections import defaultdict
from discord.ext import commands
from template import TWEET_TEMPLATE, USER_TEMPLATE

class Telegram(commands.Cog):

	def __init__(self, bot: commands.Bot, db: pymongo.database.Database):
		self.bot = bot
		self.db = db

