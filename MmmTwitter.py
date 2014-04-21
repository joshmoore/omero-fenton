import ConfigParser
import HTMLParser
import twitter
import datetime, time
import logging
import sys



def get_auth(filename=None, config=None, dance=False):
    """
    Get an authentication object that can be passed to a twitter client.
    Note this doesn't actually check the OAuth credentials are valid.
    """

    if config:
        p = config
    else:
        p = ConfigParser.SafeConfigParser()
        if not p.read(filename):
            raise Exception('Invalid configuration file: %s' % filename)

    try:
        consumer_key = p.get('twitter', 'consumer_key')
        logging.debug('consumer key: %s' % consumer_key)
        consumer_secret = p.get('twitter', 'consumer_secret')
        logging.debug('consumer secret: %s' % consumer_secret)

    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError) as e:
        raise Exception('No application consumer key/secret found, '
                        'please create one at '
                        'https://dev.twitter.com/apps/ '
                        'and edit %s' % filename)

    try:
        oauth_token = p.get('twitter', 'oauth_token')
        logging.debug('oauth_token: %s' % oauth_token)
        oauth_token_secret = p.get('twitter', 'oauth_token_secret')
        logging.debug('oauth_token_secret: %s' % oauth_token_secret)

    except ConfigParser.NoOptionError:
        logging.error('OAuth token not found')
        if not dance:
            logging.error('Please create an OAuth token')
            return

        oauth_token, oauth_token_secret = twitter.oauth_dance(
            'T2X', consumer_key, consumer_secret)
        p.set('twitter', 'oauth_token', oauth_token)
        p.set('twitter', 'oauth_token_secret', oauth_token_secret)
        p.write(open(filename, 'w'))

        logging.debug('oauth_token: %s' % oauth_token)
        logging.debug('oauth_token_secret: %s' % oauth_token_secret)

    auth = twitter.OAuth(oauth_token, oauth_token_secret,
                         consumer_key, consumer_secret)
    return auth


def get_client(resource=None, auth=None):
    if resource is None:
        client = twitter.Twitter(auth=auth)
    elif resource == 'stream':
        client = twitter.TwitterStream(auth=auth)
    elif resource == 'userstream':
        client = twitter.TwitterStream(
            auth=auth, domain="userstream.twitter.com")
    else:
        raise Exception('Unknown resource')

    logging.info('Created Twitter client, resource: %s', resource)
    return client


def format_time(dtstr):
    """
    Attempt to convert a Twitter time into the local timezone
    """
    try:
        # Assumes time is always in UTC (+0000)
        dt = datetime.datetime.strptime(dtstr, '%a %b %d %H:%M:%S +0000 %Y')
        if time.daylight:
            offset = time.altzone
        else:
            offset = time.timezone
        localdt = dt - datetime.timedelta(seconds=offset)
        s = str(localdt.time())
    except ValueError:
        s = dtstr
    return s


def format_tweet(t):
    user = t['user']['screen_name']
    text = t['text']
    urls = t['entities']['urls']
    tm = t['created_at']

    ft = text
    for u in reversed(urls):
        a = u['indices'][0]
        b = u['indices'][1]
        exp = u['expanded_url']
        ft = ft[:a] + exp + ft[b:]

    tmstr = format_time(tm)
    return '@%s: %s [%s]' % (user, HTMLParser.HTMLParser().unescape(ft), tmstr)



class MmmTwitter(object):

    def __init__(self, config=None):
        self.cbs = []
        self._stop = False
        self.config = config
        self.init_tweeter()

    def init_tweeter(self):
        # For sending tweets
        auth = get_auth(config=self.config)
        self.tweeter = get_client(auth=auth)

    def add_callback(self, cb):
        self.cbs.append(cb)

    def close(self):
        self._stop = True

    def run_one(self):
        auth = get_auth(config=self.config)
        tw = get_client('userstream', auth=auth)
        it = tw.user()
        for t in it:
            if self._stop:
                return

            # In non-blocking mode None is sometimes returned
            if not t:
                continue

            try:
                # Results (particularly the first one) may not be tweets
                tstr = format_tweet(t)
                for cb in self.cbs:
                    logging.debug('Calling callback (%s)' % tstr)
                    cb(tstr)
            except KeyError:
                e = 'Failed to format tweet: %s' % t
                logging.debug(e)
                if len(e) > 80:
                    e = e[:77] + '...'
                logging.info(e[:80])

    def run(self):
        while True:
            try:
                self.run_one()
            except twitter.TwitterHTTPError as e:
                logging.warn('Twitter error: %s' % e)

            if self._stop:
                break

    def tweet(self, msg):
        try:
            self.tweeter.statuses.update(status=msg)
        except twitter.TwitterHTTPError as e:
            raise Exception('TwitterHTTPError: %s' % e.response_data)
        except Exception as e:
            raise Exception('Unknown Twitter error: %s' % e)


def initialise(xmpp, config):
    def twitter_callback(m):
        xmpp.send_message(mto=xmpp.room, mbody=m, mtype='groupchat')

    mt = MmmTwitter(config)
    mt.add_callback(twitter_callback)
    return mt


def main():
    """
    Check whether an OAuth token exists, if not then attempt to create one.
    """
    if len(sys.argv) != 2:
        sys.stderr.write('Configuration file must be specified\n')
        sys.exit(2)
    get_auth(filename=sys.argv[1], dance=True)

if __name__ == '__main__':
    main()
