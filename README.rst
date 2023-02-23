podcast2toot
============

Posts toots for each new episode of a podcast or youtube channel.

How it works
------------

The RSS feed is fetched. Each entry's title, link and description
are analysed and used to craft and send a toot.
Tags are added for each feed, so that users can subscribe to only the feed they are interested in.

The language setting is also propagated so that users only see content in
the language they understand (and configured in their Mastodon profile).

Usage
-----

To run this:

1) create a mastodon account, for example on https://botsin.space
2) in profile, tick "This is a bot account"
3) in development, click "new application", entering rss2toot, and give write:statuses rights
4) click on the application, copy the "Your access token"
5) modify the feeds.json text file to give the feeds you want to follow
6) run MASTODON_TOKEN=youraccesstokengoeshere MASTODON_URL=botsin.space python3 podcast2toot.py
