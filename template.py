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

TWITTER_TEMPLATE = {
	"user_id": None,
	"guild_id": None,
	"tweet_token": None,
	"timeline_info":{
		"max_id": 0,
		"max_sync_id": 0,
		"min_id": 0,
		"min_sync_id": 0
		},
	"focus_info":{
		"max_id": 0,
		"max_sync_id": 0,
		"min_id": 0,
		"min_sync_id": 0
		},
	"likes_info":{
		"max_id": 0,
		"max_sync_id": 0,
		"min_id": 0,
		"min_sync_id": 0
		},
	"lists_info":{
		"max_id": 0,
		"max_sync_id": 0,
		"min_id": 0,
		"min_sync_id": 0
		},
	}

TELEGRAM_TEMPLATE = {
	"user_id": None,
	"guild_id": None,
	"tl_channel": "",
	"like_channel": "",
	"list_channel": ""
	}