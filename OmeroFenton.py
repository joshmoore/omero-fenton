#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import logging
import ast
import json
import Queue
import re
import string
from slackclient import SlackClient
import time

from configurator import configure
from configurator import getcfgkey
import diskmonitor
import taillog
import aggregator
import signal
import threading


# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout set the default encoding to UTF-8.
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


class OmeroFenton(object):
    """
    OMERO Adverse Reporting of System Events
    """

    # Based on
    # https://github.com/slackhq/python-rtmbot/blob/master/rtmbot/core.py

    def __init__(self, botname, token, channel, config=None):
        self.botname = botname
        self.channel = channel
        self.config = config

        self.started = time.strftime('%Y-%m-%d %H:%M:%S %Z')
        self.reporters = []
        self.aggregators = []
        self._log_output = Queue.Queue()

        self.slack_client = SlackClient(token)
        self.slack_call('api.test')
        logging.debug('api.test suceeded')
        self.rtm_connected = self.slack_client.rtm_connect()
        if not self.rtm_connected:
            # api.test succeeded so we can still send messages
            logging.error(
                'Real-time messaging disable, rtm_connect failed: %s',
                self.rtm_connected)

        self.last_ping = 0
        self._alive = True

    def slack_call(self, *args, **kwargs):
        r = self.slack_client.api_call(*args, **kwargs)
        if not r['ok']:
            raise Exception(str(r))

    def start(self):
        while self._alive:
            if self.rtm_connected:
                for msg in self.slack_client.rtm_read():
                    self.message(msg)
                self.autoping()
            self.output_logs()
            time.sleep(0.2)

    def autoping(self):
        # hardcode the interval to 3 seconds
        now = int(time.time())
        if now > self.last_ping + 3:
            self.slack_client.server.ping()
            self.last_ping = now

    def close(self, ret=None):
        if self._alive:
            # Graceful exit
            self._alive = False
        else:
            logging.error('Calling sys.exit(%d)' % ret)
            sys.exit(ret)

    def message(self, data):
        logging.debug('Received message %s', data)
        if data.get("type") == "message" and data.get("user"):
            # This is a real user, not a bot
            text = data.get("text")
            channel = data.get("channel")
            if text and channel:
                funcs = [self.status]
                for f in funcs:
                    reply = f(text)
                    if reply:
                        slack_channel = self.slack_client.server.channels.find(
                            channel)
                        logging.info('Replying: %s', reply)
                        slack_channel.send_message(reply)

    def log_message(self, logmsg):
        logging.info('Queuing: %s', logmsg)
        att = {
            "fallback": "Log monitor alert",
            "color": "#ff0000",
            # "pretext": "Pretext text",
            "title": "Log monitor alert",
            # "title_link": "https://api.slack.com/docs/attachments",
            # "fields": [{
            #     "title":"key", "value":"value"
            #     }],
            "ts": time.time(),
            "mrkdwn_in": ["text"],
            "text": "```\n%s\n```" % logmsg,
            }
        self._log_output.put(json.dumps([att]))

    def output_logs(self):
        try:
            log = self._log_output.get_nowait()
            self.slack_call(
                'chat.postMessage', channel=self.channel,
                username=self.botname, attachments=log)
        except Queue.Empty:
            pass

    def status(self, body):
        logging.debug(body)
        reply = None
        repunc = re.escape(string.punctuation)
        pattern = '(^|[%s\s])@?%s([%s\s]|$)' % (repunc, self.botname, repunc)
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

    def add_aggregator(self, reporter):
        self.aggregators.append(reporter)
        for r in self.reporters:
            if hasattr(r, 'add_sink'):
                r.add_sink(reporter)
        t = threading.Thread(target=reporter.start)
        t.daemon = True
        t.start()


def add_log_reporter(logtype, bot, logcfg, maincfg):
    logClass = logtype_map[logtype]

    logreq = ['name', 'file']
    if any(k not in logcfg for k in logreq):
        raise Exception('[%s] must contain keys: %s' % (logtype, logreq))

    name = getcfgkey('name', logcfg)
    filename = getcfgkey('file', logcfg)
    levels = getcfgkey('levels', logcfg, maincfg).split(',')

    limitn = getcfgkey('rate_limit_n', logcfg, maincfg, cast=int)
    limitt = getcfgkey('rate_limit_t', logcfg, maincfg, cast=float)

    r = logClass(filename, name, bot, levels, limitn, limitt)
    loglen = getcfgkey('max_log_length', logcfg, maincfg, cast=int)
    if loglen:
        r.max_log_length = loglen

    bot.add_reporter(r)


def add_disk_reporter(logtype, bot, logcfg):
    logreq = ['path', 'warn_mb', 'hysteresis_mb']
    if any(k not in logcfg for k in logreq):
        raise Exception('[%s] must contain keys: %s' % (logtype, logreq))

    path = getcfgkey('path', logcfg)
    warnlevels = getcfgkey('warn_mb', logcfg)
    warnlevels = [int(w) for w in warnlevels.split(',')]
    hysteresis = getcfgkey('hysteresis_mb', logcfg, cast=int)

    r = diskmonitor.DiskMonitor(path, bot, warnlevels, hysteresis, 5)
    bot.add_reporter(r)


def get_email_alerter(logtype, logcfg):
    logreq = ['name', 'smtp', 'email_from', 'email_to', 'email_subject']
    if any(k not in logcfg for k in logreq):
        raise Exception('[%s] must contain keys: %s' % (logtype, logreq))

    name = getcfgkey('name', logcfg)
    smtp = getcfgkey('smtp', logcfg)
    efrom = getcfgkey('email_from', logcfg)
    eto = getcfgkey('email_to', logcfg)
    eto = eto.split()
    esubject = getcfgkey('email_subject', logcfg)

    return aggregator.EmailAlerter(name, smtp, efrom, eto, esubject)


def add_email_alerter(logtype, bot, logcfg):
    logreq = ['name', 'conditions', 'delay', 'interval']
    if any(k not in logcfg for k in logreq):
        raise Exception('[%s] must contain keys: %s' % (logtype, logreq))

    # name = getcfgkey('name', logcfg)
    conditions = getcfgkey('conditions', logcfg)
    conditions = ast.literal_eval(conditions)
    delay = getcfgkey('delay', logcfg, cast=int)
    interval = getcfgkey('interval', logcfg, cast=int)

    e = get_email_alerter(logtype, logcfg)
    r = aggregator.AggregateAlerter(conditions, delay, interval)
    r.add_alerter(e)
    bot.add_aggregator(r)


def test_email_alerter(logcfgs):
    logtype = 'emailalerts'
    if logtype in logcfgs:
        for cfg in logcfgs[logtype]:
            e = get_email_alerter(logtype, cfg)
            t = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            e.alert([('Email alert test', 'test', t)])


def main():
    args, maincfg, logcfgs = configure()

    # Setup logging.
    logging.basicConfig(level=args.loglevel,
                        format='%(asctime)-15s %(levelname)-8s %(message)s')
    logging.debug(args)
    logging.debug(maincfg)
    logging.debug(logcfgs)

    # Setup the bot and register plugins
    bot = OmeroFenton(maincfg['botname'], maincfg['token'], maincfg['channel'])

    def shutdown_handler(signal=None, frame=None):
        logging.info('Shut-down signal received')
        bot.close(1)

    if args.emailtest:
        logging.info("Testing email alerts")
        test_email_alerter(logcfgs)
        return

    signal.signal(signal.SIGINT, shutdown_handler)

    postconfig = []

    for logtype in logcfgs.keys():
        for cfg in logcfgs[logtype]:
            if logtype == 'diskmonitor':
                add_disk_reporter(logtype, bot, cfg)
            elif logtype in logtype_map:
                add_log_reporter(logtype, bot, cfg, maincfg)
            else:
                postconfig.append((logtype, cfg))

    for logtype, cfg in postconfig:
        if logtype == 'emailalerts':
            add_email_alerter(logtype, bot, cfg)
        else:
            raise Exception(
                'Invalid configuration section: [%s]', logtype)

    bot.start()
    logging.info("Done")


if __name__ == '__main__':
    main()
