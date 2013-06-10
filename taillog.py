import pytail
import re



log_start_re = re.compile('^(?P<date>\d\d\d\d-\d\d-\d\d) '
                          '(?P<time>\d\d:\d\d:\d\d,\d\d\d) '
                          '(?P<level>\w+) ')

def is_log_start(m):
    return log_start_re.match(m) is not None

def taillog(filename):
    #log = pytail.LogParser(filename, message_cb, log_start_f)
    log = pytail.LogParser(filename, log_start_f=is_log_start)
    log.parse()


