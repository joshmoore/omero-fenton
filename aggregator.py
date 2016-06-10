import logging
import Queue
import re
import smtplib
import time


class AggregateAlerter(object):

    def __init__(self, conditions, delay, interval):
        """
        conditions: A 3-tuple of regular expressions which will be matched
          against (level, name, msg). Use empty or None to ignore a field
        delay: If a reportable log is received wait for this number of
          seconds before alerting to gather additional reportable events
        interval: Don't send another alert until after this time interval
          in seconds has elapsed

        Events received more than interval seconds ago will be discarded
        """
        self.conditions = conditions
        self.delay = delay
        self.interval = interval

        self.queue = Queue.Queue()
        self.alerters = []
        self.last_event = None
        self.new_events = False
        self.n_discarded = 0

        logging.debug('conditions:%s delay:%d interval:%d',
                      self.conditions, self.delay, self.interval)

    def add_alerter(self, alerter):
        self.alerters.append(alerter)

    def clear_old(self):
        now = time.time()
        if (self.last_event and not self.queue.empty() and
                (now - self.last_event) > self.interval):
            tmp = self.get_all()
            self.n_discarded += len(tmp)
            logging.info('Discarding %d events', len(tmp))

    def log_received(self, level, name, msg):
        m = (level, name, msg)
        if self.reportable(*m):
            logging.debug('Reportable log_received: %s', m)
            now = time.time()
            self.clear_old()
            self.queue.put(m)
            self.last_event = now
            self.new_events = True
        # else:
        #    logging.debug('Ignoring log_received: %s', m)

    def get_all(self):
        msgs = []
        try:
            while True:
                msgs.append(self.queue.get(block=False))
        except Queue.Empty:
            pass
        self.new_events = False
        return msgs

    def reportable(self, level, name, msg):
        for (l, n, m) in self.conditions:
            if l and not re.search(l, level, re.I):
                continue
            if n and not re.search(n, name, re.I):
                continue
            if m and not re.search(m, msg, re.I):
                continue
            return True

    def alert(self):
        pre = None
        if self.n_discarded:
            pre = 'Suppressed events: %d not shown' % self.n_discarded
            self.n_discarded = 0
        msgs = self.get_all()
        for r in self.alerters:
            logging.debug('Alerting: %s', r)
            r.alert(msgs, pre=pre)

    def start(self):
        while True:
            if self.new_events:
                logging.debug('Sleeping for %ds before emailing', self.delay)
                time.sleep(self.delay)
                logging.debug('Alerting: %s', self.alerters)
                self.alert()
                logging.debug('Sleeping for %ds', self.interval)
                time.sleep(self.interval)
                # Don't alert events that happened during the interval
                self.new_events = False
            else:
                time.sleep(2)


class EmailAlerter(object):

    def __init__(self, name, smtp, fromaddr, toaddrs, subject):
        self.name = name
        self.smtp = smtp
        self.fromaddr = fromaddr
        self.toaddrs = toaddrs
        self.subject = subject
        self.max_attempts = 3

    def alert(self, msgs, pre=None):
        headers = '\n'.join(['From: %s' % self.fromaddr,
                             'To: %s' % ', '.join(self.toaddrs),
                             'Subject: %s' % self.subject])
        preamble = 'Alert created: %s' % time.strftime(
            '%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        formatted = '\n'.join('%s: %s:\n%s' % m for m in msgs)
        if pre:
            formatted = pre + '\n\n' + formatted

        email = headers + '\n\n' + preamble + '\n\n' + formatted
        self.send(email)

    def send(self, email):
        for a in xrange(self.max_attempts):
            try:
                s = smtplib.SMTP(self.smtp)
                logging.debug('Sending email to %s', self.toaddrs)
                s.sendmail(self.fromaddr, self.toaddrs, email)
                s.quit()
                return
            except Exception as e:
                logging.error(
                    'Failed to send email on attempt %d: %s', a + 1, e)
                if a < self.max_attempts - 1:
                    time.sleep(10)

        logging.error(
            'Failed to send email after %d attempts', self.max_attempts)
