import praw
import json
from datetime import datetime

with open("../../settings.json", "r") as f:
	settings = json.loads(f.read())

reddit = praw.Reddit(client_id=settings["reddit"]["client_id"],
					client_secret=settings["reddit"]["client_secret"],
					user_agent=settings["reddit"]["user_agent"])

data = []

for submission in reddit.subreddit("showerthoughts").top(limit=1000):
	data.append({
	"title": submission.title,
	"author": submission.author.name if submission.author else None,
	"timestamp": int(submission.created_utc)
		})

print(f"posts found: {len(data)}")

with open("../json/showerthoughts.json", "w+") as f:
	f.write(json.dumps(data, indent="\t"))
