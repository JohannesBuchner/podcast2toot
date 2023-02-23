# based on https://shkspr.mobi/blog/2018/08/easy-guide-to-building-mastodon-bots/
# and https://www.bentasker.co.uk/posts/blog/software-development/writing-a-simple-mastodon-bot-to-submit-rss-items.html

import time
import json
import os
import feedparser
import requests
import hashlib

from io import StringIO
from html.parser import HTMLParser

class MLStripper(HTMLParser):
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
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def build_toot(entry):
    ''' Take the entry dict and build a toot
    '''
    toot_str = ''

    toot_str += f"{entry['title']} | "
    toot_str += f"{entry['text']}\n"

    if entry.get('author'):
        toot_str += f"Author: {entry['author']}\n"

    toot_str += f"\n{entry['link']}\n"

    # Tags to hashtags
    if len(entry['tags']) > 0:
        for tag in entry['tags']:
            toot_str += f'#{tag.replace(" ", "")} '

    return toot_str.strip()

def send_toot(en, session, mastodon_url, token, visibility, dry_run, language=None):
    ''' Turn the dict into toot text
        and send the toot
    '''

    # Turn the dict into a toot
    toot_txt = build_toot(en)

    # Build the dicts that we'll pass into requests
    headers = {
        "Authorization" : f"Bearer {token}"
        }

    # Build the payload
    data = {
        'status': toot_txt,
        'visibility': visibility
        }

    # Are we adding a content warning?
    if en.get('cw', False):
        data['spoiler_text'] = en['title']
    if language is not None:
        data['language'] = language

    # Don't send!
    if dry_run:
        print("------")
        #print(data['status'])
        print(data)
        print("------")
        return True

    try:
        resp = session.post(
            f"{mastodon_url.strip('/')}/api/v1/statuses",
            data=data,
            headers=headers
        )

        if resp.status_code == 200:
            return True
        else:
            print(f"Failed to post {en['link']}")
            print(resp.status_code)
            return False
    except:
        print(f"Urg, exception {en['link']}")
        return False


def process_feed(feed_url, cache_file):
    ''' Process the RSS feed and generate a toot for any entry we haven't yet seen
    '''
    # Load the feed, from cache if possible
    print("checking feed ...", feed_url)
    try:
        d = json.load(open(cache_file))
    except (IOError, json.decoder.JSONDecodeError):
        d = feedparser.parse(feed_url)
        with open(cache_file, 'w') as fout:
            json.dump(d, fout, default=lambda o: '')

    # Iterate over entries
    for entry in d['entries'][::-1]:
        en = {}
        en['title'] = entry['title']
        en['link'] = entry['link']
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
    mastodon_url = os.getenv('MASTODON_URL', "https://mastodon.social")
    token = os.getenv('MASTODON_TOKEN', "")
    visibility = os.getenv('MASTODON_VISIBILITY', 'public')

    # We want to be able to use keep-alives if we're posting multiple things
    # so set up a connection pool
    session = requests.session()

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
            if send_toot(en, session, mastodon_url, token, visibility, dry_run, language=feed.get('lang')):
                # If that worked, write hash to disk to prevent re-sending
                with open(feed_hash_file, 'w') as fhash:
                    fhash.write(en['link'])

            # Don't spam the API
            time.sleep(1)
            break

if __name__ == '__main__':
    main()
