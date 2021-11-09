#!/usr/bin/python3
import re
import copy
import emoji
import discord
import logging
import pymongo
import configparser
from template import GUILD_TEMPLATE
from discord.ext import commands



class Role(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser, db: pymongo.database.Database):
		self.bot = bot
		self.config = config
		self.db = db

		self.default_emoji_role_pattern = re.compile(" <@&([\d]+)> .")
		self.custom_emoji_role_pattern = re.compile(" <@&([\d]+)> (<:[a-z_]+:[\d]+>)")


	def split(self, string, splitter = "  "):
		if splitter not in string:
			return None

		split_arr = string[string.find('  ')+len(splitter):].split(splitter)
		if len(split_arr) == 1 and split_arr[0] == '':
			return None

		return split_arr



	@commands.command(pass_context=True, help="create a role and assign to the user")
	@commands.has_permissions(manage_roles=True)
	async def roleCreate(self, ctx: commands.Context):

		args = self.split(ctx.message.content)
		if not args or len(args) > 2:
			await ctx.send("Invalid parameters. Please specify the role name (and color) separated by **double spaces**. Color should be in the form of \"(r, g, b)\" if you want to specify the color.\nExample: \n\t\"roleAdd  role_name\"\n\t\"roleAdd  role_name  color\"")
			return
		
		role_name = args[0]
		
		roles = await ctx.guild.fetch_roles()
		if role_name in [role.name for role in roles]:
			await ctx.send("The role name already exists. Please choose another name.")
			return

		# Setting color
		if len(args) == 2:
			try:
				color = discord.Colour.from_rgb([int(v) for v in args[1][1:-1].split(',')])
			except:
				await ctx.send("Invalid color. Please specify the role name (and color) separated by **double spaces**. Color should be in the form of \"(r, g, b)\" if you want to specify the color.\nExample: \"roleCreate  role_name\"\n\"roleAdd  role_name  color\"")
				return

		else:
			color = discord.Colour.random()
			

		# Create the role and assign the author to this role
		role = await ctx.guild.create_role(name=role_name, color=color)
		await ctx.author.add_roles(role)



	@commands.command(pass_context=True, help="assign a role to the user")
	@commands.has_permissions(manage_roles=True)
	async def roleAdd(self, ctx: commands.Context):
		args = self.split(ctx.message.content)

		if not args or len(args) > 1:
			await ctx.send("Invalid parameters. Please specify the role name (and color) separated by **double spaces**. Color should be in the form of \"(r, g, b)\" if you want to specify the color.\nExample: \n\t\"roleAdd  role_name\"")
			return

		roles = await ctx.guild.fetch_roles()
		if args[0] not in [role.name for role in roles]:
			await ctx.send("No such role. Please specify an existing role.")
			return

		await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name=args[0]))




	@commands.command(pass_context=True, help="bind a role with emoji")
	@commands.has_permissions(manage_roles=True)
	async def roleBind(self, ctx: commands.Context):

		def getEmoji(s):
			emo = [c for c in s if c in emoji.UNICODE_EMOJI['en']]
			if emo:
				return emo[0]
			else:
				return None

		# Retrieve content
		content = ctx.message.content
		emo = getEmoji(content)
		

		# Extract role and emoji
		success_match = False
		de_content = emoji.demojize(ctx.message.content)

		default_result = self.default_emoji_role_pattern.search(de_content)
		if default_result and emo:
			role_id, emoji_to_bind = default_result.group(1), emo
			success_match = True
		
		custom_result = self.custom_emoji_role_pattern.search(content)
		if custom_result:
			role_id, emoji_to_bind = custom_result.group(1), custom_result.group(2)
			success_match = True

		# Further check if role is legal
		if success_match:
			roles = await ctx.guild.fetch_roles()
			if role_id not in [str(x.id) for x in roles]:
				success_match = False

		# No patterns found or role invalid
		if not success_match:
			await ctx.send("Please follow the syntax to bind emoji to the role.\n\
							\t=roleBind role_to_bind emoji_to_represent")
			return


		# Bind role and emoji, save into database
		query_result = self.db["guild_info"].find_one({"guild_id": ctx.guild.id})

		if not query_result:

			data_entry = copy.deepcopy(GUILD_TEMPLATE)
			data_entry["guild_id"] = ctx.guild.id
			data_entry["roles"][role_id] = emoji_to_bind
			self.db["guild_info"].insert_one(data_entry)

		else:

			if role_id in query_result['roles'].keys():
				await ctx.send("This role already has its emoji.")
			else:
				self.db["guild_info"].update_one(query_result, {"$set": {
					"roles."+role_id: emoji_to_bind
				}})



	@commands.command(pass_context=True, help="role reactive message")
	@commands.has_permissions(manage_roles=True)
	async def roleReact(self, ctx: commands.Context):

		query_result = self.db["guild_info"].find_one({"guild_id": ctx.guild.id})
		if not query_result:
			await ctx.send("No roles available.")
			return

		msg = await ctx.send("Select your roles to bind")
		self.db["guild_info"].update_one(query_result, {"$set": {
					"role_react_id": msg.id
				}})

		for emo in query_result["roles"].values():
			await msg.add_reaction(emo)



	@commands.Cog.listener()
	async def on_raw_reaction_add(self, reaction_payload):

		user = await self.bot.fetch_user(reaction_payload.user_id)
		if user == self.bot.user:
			return

		guild = await self.bot.fetch_guild(reaction_payload.guild_id)
		channel = await self.bot.fetch_channel(reaction_payload.channel_id)
		message = await channel.fetch_message(reaction_payload.message_id)
		emo = str(reaction_payload.emoji)


		query_result = self.db["guild_info"].find_one({"guild_id": guild.id})
		if not query_result:
			return

		self.bot.fetch_offline_members = True
		member = await guild.query_members(user_ids=[user.id])[0]

		if query_result:

			if message.id == query_result['role_react_id']:
				for role_id, e in query_result['roles'].items():
					if e == emo:
						await member.add_roles(discord.utils.get(guild.roles, id=int(role_id)))
						return