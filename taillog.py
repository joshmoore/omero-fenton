import pytail
import re
import logging


class LogReporter(object):

    def __init__(self, file, name, arse, levels):
        self.file = file
        self.name = name
        self.arse = arse
        self.levels = levels

        self.log_re = re.compile('^(?P<date>\d\d\d\d-\d\d-\d\d) '
                                 '(?P<time>\d\d:\d\d:\d\d,\d\d\d) '
                                 '(?P<level>\w+) ')
        self.max_log_length = 4096
        self.counts = dict.fromkeys(self.levels, 0)

    def is_log_start(self, m):
        logging.debug('is_log_start: %s', m)
        match = self.log_re.match(m) if m else None
        return (match is not None, match)

    def log_received(self, msg, match):
        logging.debug('log_received: %s', msg)
        level = match.groupdict()['level']
        if level in self.levels:
            self.counts[level] += 1
            m = '%s: %s:\n%s' % (level, self.name, msg[:self.max_log_length])
            self.arse.log_message(m)

    def taillog(self):
        pollint = 2
        block = False
        log = pytail.LogParser(self.file, self.log_received, self.is_log_start,
                               pollint, block)
        log.parse()

    def start(self):
        self.taillog()

    def status(self):
        m = '%s:    %s' % (
            self.name, '  '.join('%s: %d' % c for c in self.counts.iteritems()))
        logging.debug('status: %s', m)
        return m



