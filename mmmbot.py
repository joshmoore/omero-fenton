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

# Don't use the system version, might be out of date
sys.path.insert(0, os.path.join(
        os.path.dirname( __file__ ), 'SleekXMPP/build/lib'))
import sleekxmpp

from difflib import SequenceMatcher
import itertools
import string
import re


# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    raw_input = input


def is_morning(s, nick=None):
    def canonicalise(s):
        delchars = string.punctuation + string.whitespace
        if isinstance(s, unicode):
            deltable = {ord(a): None for a in delchars}
            s = s.translate(deltable).lower()
        else:
            s = s.translate(None, delchars).lower()
        t = ''.join([a if a != b else '' for a, b in
                     itertools.izip(s[:-1], s[1:])])
        return t

    def sim(ref, t):
        ref = canonicalise(ref)
        t = canonicalise(t)
        r = SequenceMatcher(lambda x:x in ' ', ref, t).ratio()
        return r

    refs1 = ['morning', 'good morning', 'hello', 'hi']
    refs2 = ['', ' all', ' everyone']
    if nick:
        refs2.append(' ' + nick)
    refs = [''.join(x) for x in itertools.product(refs1, refs2)]
    logging.debug('Reference messages: %s', refs)

    resp1 = ['morning', 'morning', 'hello', 'hi']
    resp2 = [''] * len(refs2)
    resp = [''.join(x) for x in itertools.product(resp1, resp2)]

    r = map(lambda ref: sim(ref, s), refs)
    logging.debug('Scores: %s', r)
    mr = max(r)
    mri = r.index(mr)
    return (mr, refs[mri], resp[mri])






class MmmBot(sleekxmpp.ClientXMPP):

    """
    A simple SleekXMPP bot that will greets those
    who enter the room, and acknowledge any messages
    that mentions the bot's nickname.
    """

    def __init__(self, jid, password, room, nick):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.nick = nick

        self._get_compiled_res()
        self._get_exact_greetings()

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

        # The groupchat_presence event is triggered whenever a
        # presence stanza is received from any chat room, including
        # any presences you send yourself. To limit event handling
        # to a single room, use the events muc::room@server::presence,
        # muc::room@server::got_online, or muc::room@server::got_offline.
        #self.add_event_handler("muc::%s::got_online" % self.room,
        #                       self.muc_online)


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
            funcs = [self.fuzzy_greeting, self.exact_greeting, self.beer]
            for f in funcs:
                reply = f(body, mucnick)
                if reply:
                    logging.info('Replying: %s', reply)
                    self.send_message(mto=msg['from'].bare,
                                      mbody=reply,
                                      mtype='groupchat')
                    return



    def fuzzy_greeting(self, body, user):
        reply = None
        s = self._strip(body)
        r, val, resp = is_morning(s, self.nick)
        if r > 0.9 or (r > 0.8 and len(val.split()) == 1):
            reply = '%s %s' %(resp, user)
        return reply

    def exact_greeting(self, body, user):
        reply = None
        s = self._strip(body)
        if s in self.greetings_list:
            reply = '%s %s' %(s, user)
        return reply



    def beer(self, body, user):
        reply = None
        if self._beer_rec.search(body):
            reply = u'%botsnack be\u202ere'
        return reply



    def _strip(self, s):
        return self._stripper_rec.match(s.lower()).group(1)

    def _get_compiled_res(self):
        repunc = re.escape(string.punctuation + string.whitespace)
        self._stripper_rec = re.compile(
            '^[%s]*(.*?)[%s]*$' %(repunc, repunc), re.DOTALL)
        self._beer_rec = re.compile('(^|[%s])beer($|[%s])' % (repunc, repunc))

    def _get_exact_greetings(self):
        d = os.path.dirname( __file__ )
        filename = os.path.join(d, 'hello.txt')
        hdict = {}
        with open(filename) as f:
            for ln in f:
                if ln.lstrip().startswith('#'):
                    continue
                k, vs = ln.split(':')
                hdict[k.strip()] = [v.strip() for v in vs.split(',')]
        self.greetings_list = set(itertools.chain.from_iterable(hdict.values()))




if __name__ == '__main__':
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

    opts, args = optp.parse_args()

    # Setup logging.
    logging.basicConfig(level=opts.loglevel,
                        format='%(levelname)-8s %(message)s')

    if opts.jid is None:
        opts.jid = raw_input("Username: ")
    if opts.password is None:
        opts.password = getpass.getpass("Password: ")
    if opts.room is None:
        opts.room = raw_input("MUC room: ")
    if opts.nick is None:
        opts.nick = raw_input("MUC nickname: ")

    # Setup the MUCBot and register plugins. Note that while plugins may
    # have interdependencies, the order in which you register them does
    # not matter.
    xmpp = MmmBot(opts.jid, opts.password, opts.room, opts.nick)
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0199') # XMPP Ping

    # Connect to the XMPP server and start processing XMPP stanzas.
    if xmpp.connect():
        # If you do not have the dnspython library installed, you will need
        # to manually specify the name of the server if it does not match
        # the one in the JID. For example, to use Google Talk you would
        # need to use:
        #
        # if xmpp.connect(('talk.google.com', 5222)):
        #     ...
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect.")
