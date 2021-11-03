#!/usr/bin/python3

import discord
import logging
import configparser
from discord.ext import commands


class Role(commands.Cog):

	def __init__(self, bot: commands.Bot, config: configparser.ConfigParser):
		self.bot = bot
		self.config = config



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


		if len(args) == 2:
			try:
				color = discord.Colour.from_rgb([int(v) for v in args[1][1:-1].split(',')])
			except:
				await ctx.send("Invalid color. Please specify the role name (and color) separated by **double spaces**. Color should be in the form of \"(r, g, b)\" if you want to specify the color.\nExample: \"roleCreate  role_name\"\n\"roleAdd  role_name  color\"")
				return

		else:
			color = discord.Colour.random()
			
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


		
