#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    SleekXMPP: The Sleek XMPP Library
    Copyright (C) 2010  Nathanael C. Fritz
    This file is part of SleekXMPP.

    See the file LICENSE for copying permission.
"""

import sys
import os.path
import logging
import getpass
from optparse import OptionParser
import ConfigParser

import sleekxmpp

from difflib import SequenceMatcher
import itertools
import string
import re
from random import choice
import MmmTwitter
import signal



# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    raw_input = input


class JabberTwitterBot(sleekxmpp.ClientXMPP):

    """
    A simple SleekXMPP bot that will post Twtitter statuses from Jabber.
    """

    def __init__(self, jid, password, room, nick, config=None):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.nick = nick

        self.config = config

        self._output_plugins = []
        self.twitter = None

        # The session_start event will be triggered when
        # the bot establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start)

        # The groupchat_message event is triggered whenever a message
        # stanza is received from any chat room. If you also also
        # register a handler for the 'message' event, MUC messages
        # will be processed by both handlers.
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("message", self.message)

        # The groupchat_presence event is triggered whenever a
        # presence stanza is received from any chat room, including
        # any presences you send yourself. To limit event handling
        # to a single room, use the events muc::room@server::presence,
        # muc::room@server::got_online, or muc::room@server::got_offline.
        #self.add_event_handler("muc::%s::got_online" % self.room,
        #                       self.muc_online)

    def get_config_option(self, key):
        try:
            val = self.config.get('twitterbot', key)
        except Exception as e:
            logging.error('get_config_option: %s' % e)
            val = None
        return val

    def add_output_plugin(self, op):
        self._output_plugins.append(op)
        logging.debug('Added output plugin %s' % op)
        try:
            op.run()
            logging.debug('Running output plugin %s' % op)
        except Exception as e:
            logging.error('[%s].run() failed: %s' % (op, e))
            try:
                op.close()
            except Exception as e:
                logging.error('[%s].close() failed: %s' % (op, e))

    def set_twitter(self, twitter):
        self.twitter = twitter
        self.add_output_plugin(twitter)

    def start(self, event):
        """
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Arguments:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        """
        self.get_roster()
        self.send_presence()
        self.plugin['xep_0045'].joinMUC(self.room,
                                        self.nick,
                                        # If a room password is needed, use:
                                        # password=the_room_password,
                                        wait=True)


    def close(self, ret=None):
        try:
            logging.debug('Calling scheduler.quit()')
            self.scheduler.quit()
        except Exception as e:
            logging.info(e)

        for op in self._output_plugins:
            try:
                logging.debug('Calling [%s].close()' % op)
                op.close()
            except Exception as e:
                logging.error('[%s].close() failed: %s' % (op, e))

        try:
            logging.debug('Calling abort()')
            self.abort()
        except Exception as e:
            logging.error(e)

        if ret is not None:
            logging.debug('Calling sys.exit(%d)' % ret)
            sys.exit(ret)


    def muc_message(self, msg):
        """
        Process incoming message stanzas from any chat room. Be aware
        that if you also have any handlers for the 'message' event,
        message stanzas may be processed by both handlers, so check
        the 'type' attribute when using a 'message' event handler.

        Whenever the bot's nickname is mentioned, respond to
        the message.

        IMPORTANT: Always check that a message is not from yourself,
                   otherwise you will create an infinite loop responding
                   to your own messages.

        This handler will reply to messages that mention
        the bot's nickname.

        Arguments:
            msg -- The received message stanza. See the documentation
                   for stanza objects and the Message stanza to see
                   how it may be used.
        """

        # We're in unicode mode, assume all strings are unicode
        mucnick = str(msg['mucnick'])
        body = str(msg['body'])
        if mucnick != self.nick and mucnick.find('-bot') < 0:
            funcs = [self.tweet, self.status, self.shutup]
            for f in funcs:
                reply = f(body, mucnick)
                if reply:
                    logging.info('Replying: %s', reply)
                    self.send_message(mto=msg['from'].bare,
                                      mbody=reply,
                                      mtype='groupchat')
                    return


    def message(self, msg):
        if msg['type'] in ('chat', 'normal'):
            logging.info('Received direct message:%s from:%s body:%s' % (
                    msg, msg['from'].bare, msg['body']))

        if msg['body'] == 'shut-up mmm-bot':
            admins = self.get_config_option('botadmins')
            if admins:
                if msg['from'].bare in admins.split():
                    logging.info('Admin message received')

    def tweet(self, body, nick):
        reply = None
        p = '(\s|^)#tweetme(\s|$)'
        s = body.strip()
        logging.debug('tweet(%s)', body)
        if self.twitter and re.search(p, body, re.IGNORECASE):
            s = re.sub(p, ' ', s, re.IGNORECASE)
            s = re.sub('\s+', ' ', s)
            try:
                logging.info('Tweeting: %s', s)
                self.twitter.tweet(s)
                reply = 'Tweet sent'
            except Exception as e:
                logging.error('Error: %s', e)
                reply = str(e)
        return reply

    def status(self, body, nick):
        logging.debug(body)
        reply = None
        repunc = re.escape(string.punctuation)
        pattern = '(^|[%s\s])%s([%s\s]|$)' % (repunc, self.nick, repunc)
        if re.search(pattern, body, re.IGNORECASE):
            reply = ('Hi, I\'m the OME Twitter bot. '
                     'To tweet from this room include #tweetme in your message')
        return reply

    def shutup(self, body, user):
        if body == 'shut-up %s' % self.nick:
            logging.info('shut-up received')
            self.close(2)

def main():
    # Setup the command line arguments.
    optp = OptionParser()

    # Output verbosity options.
    optp.add_option('-q', '--quiet', help='set logging to ERROR',
                    action='store_const', dest='loglevel',
                    const=logging.ERROR, default=logging.INFO)
    optp.add_option('-d', '--debug', help='set logging to DEBUG',
                    action='store_const', dest='loglevel',
                    const=logging.DEBUG, default=logging.INFO)
    optp.add_option('-v', '--verbose', help='set logging to COMM',
                    action='store_const', dest='loglevel',
                    const=5, default=logging.INFO)

    # JID and password options.
    optp.add_option("-j", "--jid", dest="jid",
                    help="JID to use")
    optp.add_option("-p", "--password", dest="password",
                    help="password to use")
    optp.add_option("-r", "--room", dest="room",
                    help="MUC room to join")
    optp.add_option("-n", "--nick", dest="nick",
                    help="MUC nickname")

    # Configuration file
    optp.add_option("-f", "--config", dest="config",
                    help="Configuration file")

    opts, args = optp.parse_args()

    config = ConfigParser.SafeConfigParser()
    if opts.config:
        if not config.read(opts.config):
            raise Exception('Invalid configuration file: %s' % opts.config)

    # Setup logging.
    logging.basicConfig(level=opts.loglevel,
                        format='%(levelname)-8s %(message)s')

    # Check opts followed by config file for parameters
    def opts_or_config(o, c, n):
        if o is None:
            try:
                o = config.get('twitterbot', c)
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                if n:
                    o = raw_input("%s: " % n)
        return o

    opts.jid = opts_or_config(opts.jid, 'jid', 'Username')
    opts.password = opts_or_config(opts.password, 'password', None)
    if opts.password is None:
        opts.password = getpass.getpass("Password: ")
    opts.room = opts_or_config(opts.room, 'room', 'MUC room')
    opts.nick = opts_or_config(opts.nick, 'nick', 'MUC nickname')

    # Setup the MUCBot and register plugins. Note that while plugins may
    # have interdependencies, the order in which you register them does
    # not matter.
    xmpp = JabberTwitterBot(opts.jid, opts.password, opts.room, opts.nick, config)
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0199') # XMPP Ping


    def shutdown_handler(signal=None, frame=None):
        logging.info('Shut-down signal received')
        xmpp.close(1)

    # Connect to the XMPP server and start processing XMPP stanzas.
    maincfg = dict(config.items('twitterbot'))
    if 'server' in maincfg:
        host = maincfg['server']
        try:
            host, port = host.rsplit(':', 1)
            port = int(port)
        except ValueError:
            port = 5222
        r = xmpp.connect((host, port))
    else:
        r = xmpp.connect()

    if r:
        # If you do not have the dnspython library installed, you will need
        # to manually specify the name of the server if it does not match
        # the one in the JID. For example, to use Google Talk you would
        # need to use:
        #
        # if xmpp.connect(('talk.google.com', 5222)):
        #     ...
        signal.signal(signal.SIGINT, shutdown_handler)
        #xmpp.process(block=True)
        xmpp.process(block=False)

        xmpp.set_twitter(MmmTwitter.initialise(xmpp, config))

        #xmpp.process(block=True)

        print("Done")
    else:
        print("Unable to connect.")


if __name__ == '__main__':
    main()
