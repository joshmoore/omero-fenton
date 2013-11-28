import os
import time
import logging


class DiskMonitor(object):

    def __init__(self, path, arse, warn1=2048, warn2=1024, hys=512, delay=60):
        self.path = path
        self.arse = arse
        self.warn1 = warn1
        self.warn2 = warn2
        self.hysteresis = hys
        self.delay = delay
        self.state = 0

    def get_disk_space(self, superuser=False):
        def block2mb(b):
            return float(b) * s.f_bsize / 1024 / 1024

        s = os.statvfs(self.path)
        total_mb = block2mb(s.f_blocks)
        if superuser:
            free_mb = block2mb(s.f_bfree)
        else:
            free_mb = block2mb(s.f_bavail)

        logging.debug('free_mb:%f total_mb:%f', free_mb, total_mb)
        return free_mb, total_mb

    def check_space(self):
        free_mb, total_mb = self.get_disk_space()

        if free_mb <= self.warn1:
            logging.debug('free_mb <= warn1')
            newstate = max(self.state, 1)
        if free_mb <= self.warn2:
            logging.debug('free_mb <= warn2')
            newstate = max(self.state, 2)
        if free_mb > self.warn2 + self.hysteresis:
            logging.debug('free_mb > warn2 + hysteresis')
            newstate = min(self.state, 1)
        if free_mb > self.warn1 + self.hysteresis:
            logging.debug('free_mb > warn1 + hysteresis')
            newstate = min(self.state, 0)

        logging.debug('state current:%s new:%s', self.state, newstate)
        if newstate > self.state:
            self.notify(newstate, free_mb, total_mb)
        self.state = newstate

    def format_free_space(self, free_mb, total_mb):
        def fmt(n):
            if n > 1024:
                return '%.1f GiB' % (n / 1024.0)
            return '%.1f MiB' % n

        m = '%s: %s of %s (%.1f%%) free' % (
            self.path, fmt(free_mb), fmt(total_mb), free_mb * 100 / total_mb)
        return m

    def notify(self, state, free_mb, total_mb):
        emph = ''
        if state > 0:
            emph = ('*' * 50 + '\n') * state
        mfree = self.format_free_space(free_mb, total_mb)
        m = '%sDISK SPACE WARNING: %s\n%s' % (emph, mfree, emph)
        self.arse.log_message(m)

    def start(self):
        while True:
            self.check_space()
            time.sleep(self.delay)

    def status(self):
        m = self.format_free_space(*self.get_disk_space())
        logging.debug('status: %s', m)
        m = 'Disk space: ' + m
        return m


