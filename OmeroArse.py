#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import logging
import argparse
import ConfigParser
import re
import string
import sleekxmpp
import time

from configurator import configure
from configurator import getcfgkey
import diskmonitor
import taillog
import signal
import threading


# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    raw_input = input


logtype_map = {
    'logdefault': taillog.LimitLogReporter,
    'logall': taillog.LimitLogAllReporter,
    'logdatelevel': taillog.LimitLogDateLevelReporter,
    }



class OmeroArse(sleekxmpp.ClientXMPP):
    """
    OMERO Adverse Reporting of System Events
    """

    def __init__(self, jid, password, room, nick, config=None):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.nick = nick

        self.config = config

        self.started = time.strftime('%Y-%m-%d %H:%M:%S %Z')

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

        self.reporters = []

    def get_config_option(self, key):
        try:
            val = self.config.get('mmmbot', key)
        except Exception as e:
            logging.error('get_config_option: %s' % e)
            val = None
        return val

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

        # If this is a new room it needs to be configured before anyone else can join.
        # Not sure how you're meant to do that though.
        # https://github.com/chatmongers/chatmongers-web-demos/blob/master/muc_event_subscription/mucsetup.py
        # https://github.com/skinkie/SleekXMPP--XEP-0080-/blob/master/sleekxmpp/plugins/xep_0045.py
        try:
            self.plugin['xep_0045'].configureRoom(self.room)
        except Exception as e:
            logging.error('xep_0045.configureRoom: %s', e)

    def close(self, ret=None):
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
        """

        # We're in unicode mode, assume all strings are unicode
        mucnick = str(msg['mucnick'])
        body = str(msg['body'])
        if mucnick != self.nick and mucnick.find('-bot') < 0:
            funcs = [self.status]
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

        if msg['body'] == 'shut-up ' + self.nick:
            admins = self.get_config_option('botadmins')
            if admins:
                if msg['from'].bare in admins.split():
                    logging.info('Admin message received')
                    self.close(0)


    def log_message(self, logmsg):
        logging.info('Sending: %s', logmsg)
        self.send_message(mto=self.room, mbody=logmsg, mtype='groupchat')

    #def send_message(self, mto, mbody, mtype):
    #    print mto, mtype, mbody


    def status(self, body, nick):
        logging.debug(body)
        reply = None
        repunc = re.escape(string.punctuation)
        pattern = '(^|[%s\s])%s([%s\s]|$)' % (repunc, self.nick, repunc)
        if re.search(pattern, body, re.IGNORECASE):
            reply = 'OMERO Adverse Reporting of System Errors\n\n'
            reply += 'Monitoring started: %s\n' % self.started
            for r in self.reporters:
                reply += r.status() + '\n'
        return reply


    def add_reporter(self, reporter):
        self.reporters.append(reporter)
        t = threading.Thread(target=reporter.start)
        t.daemon = True
        t.start()



def add_log_reporter(logtype, xmpp, logcfg, maincfg):
    logClass = logtype_map[logtype]

    logreq = ['name', 'file']
    if any(k not in logcfg for k in logreq):
        raise Exception('[%s] must contain keys: %s' % (s, logreq))

    name = getcfgkey('name', logcfg)
    filename = getcfgkey('file', logcfg)
    levels = getcfgkey('levels', logcfg, maincfg).split(',')

    limitn = getcfgkey('rate_limit_n', logcfg, maincfg, cast=int)
    limitt = getcfgkey('rate_limit_t', logcfg, maincfg, cast=float)

    r = logClass(filename, name, xmpp, levels, limitn, limitt)
    loglen = getcfgkey('max_log_length', logcfg, maincfg, cast=int)
    if loglen:
        r.max_log_length = loglen

    xmpp.add_reporter(r)

def add_disk_reporter(xmpp, logcfg):
    logreq = ['path', 'warn_mb', 'hysteresis_mb']
    if any(k not in logcfg for k in logreq):
        raise Exception('[%s] must contain keys: %s' % (s, logreq))

    path = getcfgkey('path', logcfg)
    warnlevels = getcfgkey('warn_mb', logcfg)
    warnlevels = [int(w) for w in warnlevels.split(',')]
    hysteresis = getcfgkey('hysteresis_mb', logcfg, cast=int)

    r = diskmonitor.DiskMonitor(path, xmpp, warnlevels, hysteresis, 5)
    xmpp.add_reporter(r)

def main():
    args, maincfg, logcfgs = configure()

    # Setup logging.
    logging.basicConfig(level=args.loglevel,
                        format='%(levelname)-8s %(message)s')
    logging.debug(args)
    logging.debug(maincfg)
    logging.debug(logcfgs)

    # Setup the MUCBot and register plugins. Note that while plugins may
    # have interdependencies, the order in which you register them does
    # not matter.
    xmpp = OmeroArse(maincfg['jid'], maincfg['password'],
                     maincfg['room'], maincfg['nick'])

    # This may or may not be needed for ['xep_0045'].configureRoom
    xmpp.register_plugin('xep_0004') # Data Forms

    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0199') # XMPP Ping


    def shutdown_handler(signal=None, frame=None):
        logging.info('Shut-down signal received')
        xmpp.close(1)

    # Connect to the XMPP server and start processing XMPP stanzas.
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

        for logtype in logcfgs.keys():
            for cfg in logcfgs[logtype]:
                if logtype == 'diskmonitor':
                    add_disk_reporter(xmpp, cfg)
                elif logtype in logtype_map:
                    add_log_reporter(logtype, xmpp, cfg, maincfg)
                else:
                    raise Exception(
                        'Invalid configuration section: [%s]', logtype)

        xmpp.process(block=True)
        #xmpp.process(block=False)

        logging.info("Done")
    else:
        logging.error("Unable to connect.")


if __name__ == '__main__':
    main()
