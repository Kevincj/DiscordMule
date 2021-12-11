import bson

GUILD_TEMPLATE = {
	"guild_id": None,
	"roles": {},
	"role_react_id": None,
	"reactable_channels": [],
	"forwarding_channels": {
		"img": None,
		"vid": None
		}
	}

TWEET_TEMPLATE = {
	"tweet_id": None,
	"media_urls": [],
	"author_id": None,
	"liked": False,
	"likes": 0,
	"retweets": 0,
	"user_id": None,
	"guild_id": None
	}

INFO_TEMPLATE = {
	"max_id": bson.Int64(0),
	"max_sync_id": bson.Int64(0),
	"min_id": bson.Int64(0),
	"min_sync_id": bson.Int64(0)
	}

TWITTER_TEMPLATE = {
	"user_id": None,
	"guild_id": None,
	"tweet_token": None,
	"timeline_info":INFO_TEMPLATE,
	"self_like_info":INFO_TEMPLATE,
	"focus_info":{},
	"likes_info":{},
	"lists_info":{}
	}


TELEGRAM_TEMPLATE = {
	"user_id": None,
	"guild_id": None,
	"tl_channel": "",
	"like_channel": "",
	"list_channel": ""
	}