"""podcast2toot.py

To run this:
1) create a mastodon account, for example on botsin.space
2) in profile, tick "This is a bot account"
3) in development, click "new application", entering rss2toot, and give write:statuses rights
4) click on the application, copy the "Your access token"
5) modify the feeds.json file to give the feeds you want to follow
6) run MASTODON_TOKEN=youraccesstokengoeshere MASTODON_URL=botsin.space python3 podcast2toot.py

"""

# based on https://shkspr.mobi/blog/2018/08/easy-guide-to-building-mastodon-bots/
# and https://www.bentasker.co.uk/posts/blog/software-development/writing-a-simple-mastodon-bot-to-submit-rss-items.html

import time
import json
import os
import sys
import hashlib
import feedparser
from io import StringIO
from html.parser import HTMLParser

from mastodon import Mastodon

class MLStripper(HTMLParser):
    """Helper for removing remaining markup tags."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()
    def handle_data(self, d):
        self.text.write(d)
    def get_data(self):
        return self.text.getvalue()

def strip_tags(html):
    """Remove remaining HTML tags and return text only."""
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def build_toot(entry):
    '''Create the toot text with tags and link, not exceeding 500 characters.'''
    toot_str = '%(title)s ' % entry

    if entry.get('author') is not None:
        toot_str += ' by %(author)s ' % entry

    toot_str += ' '.join('#' + tag.replace(' ', '') for tag in entry.get('tags', [])) + " "
    
    # links are counted as 23 characters long at most
    len_current = len(toot_str) + max(23, len(entry['link']))
    # how much do we have left?
    len_remaining = max(0, 500 - len_current)
    if len_remaining >= len(entry['text']):
        toot_str += entry['text']
    else:
        toot_str += entry['text'][:len_remaining - 3] + "…"
    toot_str += "\n" + entry['link']

    return toot_str

def send_toot(en, session, visibility, dry_run, language=None):
    """Turn the dict into toot text and send the toot"""

    toot_txt = build_toot(en)

    print("------")
    print(visibility, language, "::")
    print(toot_txt)
    print("------")
    if not dry_run:
        return session.status_post(
            toot_txt[:500], sensitive=False,
            visibility=visibility, language=language
        )


def process_feed(feed_url, cache_file):
    """Get each new feed entry"""
    # Load the feed, from cache if possible
    print("checking feed ...", feed_url)
    try:
        d = json.load(open(cache_file))
        print("   loaded from cache:", cache_file)
    except (IOError, json.decoder.JSONDecodeError):
        d = feedparser.parse(feed_url)
        with open(cache_file, 'w') as fout:
            json.dump(d, fout, default=lambda o: '')

    # Iterate over entries
    for entry in d['entries'][::-1]:
        en = {}
        en['title'] = entry['title']
        en['link'] = entry['link']
        for link in entry.get('links', []):
            if link['type'].startswith('audio') or link['type'].startswith('video'):
                en['link'] = link['href']
        en['author'] = False       
        en['tags'] = [x['term'] for x in entry.get('tags', [])]
        en['author'] = entry.get('author')
        en['text'] = strip_tags(entry['summary'][:500])

        yield en


def main():
    # Load feed info
    
    feeds = json.load(open("feeds.json"))

    # Get config from env vars
    hash_dir = os.getenv('HASH_DIR', 'hashes/')
    # if Y, toots won't be sent and we'll write to stdout instead
    dry_run = os.getenv('DRY_RUN', "N") != "N"

    # Mastodon config
    if 'MASTODON_TOKEN' not in os.environ:
        sys.stderr.write(__doc__)
        sys.exit(1)
    mastodon_url = os.environ['MASTODON_URL']
    token = os.environ['MASTODON_TOKEN']
    visibility = os.getenv('MASTODON_VISIBILITY', 'public')

    session = Mastodon(access_token=token, api_base_url=mastodon_url)
    # We want to be able to use keep-alives if we're posting multiple things
    # so set up a connection pool

    # Iterate over the feeds in the config file
    for feed in feeds:
        feed_url = feed['url']
        # Define the state tracking file
        cache_file = hash_dir + hashlib.sha1(feed_url.encode('utf-8')).hexdigest()
        # Process the feed
        for en in process_feed(feed_url, cache_file=cache_file):
            linkhash = hashlib.sha1(en['link'].encode('utf-8')).hexdigest()
            feed_hash_file = cache_file + '_' + linkhash
            if 'stop' in feed:
                en['text'] = en['text'].split(feed['stop'])[0]
            en['tags'] += feed['tags']

            if os.path.exists(feed_hash_file):
                print("known entry", en['link'])
                continue

            # Send the toot
            if send_toot(en, session, visibility, dry_run, language=feed.get('lang')):
                # If that worked, write hash to disk to prevent re-sending
                with open(feed_hash_file, 'w') as fhash:
                    fhash.write(en['link'])

            # Don't spam the API
            time.sleep(1)
            break

if __name__ == '__main__':
    main()
