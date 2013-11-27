import pytail
import re
import logging
import time


class LogReporter(object):

    def __init__(self, file, name, arse, levels):
        self.file = file
        self.name = name
        self.arse = arse
        self.levels = levels

        self.log_re = re.compile('^(?P<date>\d\d\d\d-\d\d-\d\d) '
                                 '(?P<time>\d\d:\d\d:\d\d,\d\d\d) '
                                 '(?P<level>\w+) ')
        self.max_log_length = 1024
        self.counts = dict.fromkeys(self.levels, 0)

    def is_log_start(self, m):
        logging.debug('is_log_start: %s', m)
        match = self.log_re.match(m) if m else None
        return (match is not None, match)

    def truncate_msg(self, msg):
        if len(msg) > self.max_log_length:
            msg = msg[:self.max_log_length] + '...'
        return msg

    def log_received(self, msg, match):
        logging.debug('log_received: %s', msg)
        level = match.groupdict()['level']
        if level in self.levels:
            self.counts[level] += 1
            m = '%s: %s:\n%s' % (level, self.name, self.truncate_msg(msg))
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



class LimitLogReporter(LogReporter):

    def __init__(self, file, name, arse, levels, limitn=None, limitt=None,
                 matchall=False):
        super(LimitLogReporter, self).__init__(file, name, arse, levels)
        self.rate_limit_n = limitn
        self.rate_limit_t = limitt
        self.ts = []
        self.n_suppressed = 0

        # Matches all levels
        self.level_wildcard = '*'
        if matchall:
            # Override the log start regexp
            # Note logs all levels
            self.log_re = re.compile('^\S')
        logging.debug('log_re:%s', self.log_re.pattern)
        logging.debug('rate_limit_n:%d rate_limit_t:%d',
                      self.rate_limit_n, self.rate_limit_t)

    def log_received(self, msg, match):
        logging.debug('log_received: %s', msg)
        try:
            level = match.groupdict()['level']
        except KeyError:
            level = None
        if (level in self.levels or self.level_wildcard in self.levels or
            level is None):
            if level is None:
                level = self.level_wildcard
            try:
                self.counts[level] += 1
            except KeyError:
                self.counts[level] = 1
            m = '%s: %s:\n%s' % (level, self.name, self.truncate_msg(msg))
            self.log_or_limit(m)

    def warn_suppress(self):
        m = '%s: Rate limiting messages (%d / %gs)' % (
            self.name, self.rate_limit_n, self.rate_limit_t)
        self.arse.log_message(m)

    def output(self, t, msg):
        if self.n_suppressed > 0:
            s = '%s: Rate limit: %d messages not shown' % (
                self.name, self.n_suppressed)
            self.arse.log_message(s)
            self.n_suppressed = 0

        self.arse.log_message(msg)
        if self.rate_limit_n and self.rate_limit_t:
            self.ts.append(t)

    def log_or_limit(self, msg):
        now = time.time()
        logging.debug('now:%s ts:[%d]:%s n_suppressed:%d',
                      now, len(self.ts), self.ts, self.n_suppressed)
        if not self.ts:
            self.output(now, msg)
        elif now - self.ts[0] < self.rate_limit_t:
            if len(self.ts) < self.rate_limit_n:
                self.output(now, msg)
            else:
                if self.n_suppressed == 0:
                    self.warn_suppress()
                self.n_suppressed += 1
        else:
            while self.ts and now - self.ts[0] >= self.rate_limit_t:
                self.ts.pop()
            self.output(now, msg)


