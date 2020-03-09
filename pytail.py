import errno
import os
import stat
import time
import logging
# Handles pipes properly
from io import open


class PyTail(object):
    """
    A polling version of the unix 'tail -F' command
    """

    def __init__(self, filename, pollint=0.5, block=True):
        self.filename = filename
        self.pollint = pollint
        self.block = block
        self.count = 0
        self.current_inode = None

    def read_to_end(self, f):
        for line in f:
            yield line
            self.count += 1

        if not self.block:
            yield None

    def has_changed(self):
        return os.stat(self.filename).st_ino != self.current_inode

    def tail1(self):
        try:
            with open(self.filename, errors='replace') as f:
                inode = os.fstat(f.fileno()).st_ino
                if self.current_inode is None:
                    try:
                        f.seek(0, 2)
                    except IOError:
                        # Could be a unix named pipe
                        try:
                            ispipe = stat.S_ISFIFO(
                                os.fstat(f.fileno()).st_mode)
                        except:
                            ispipe = False
                        if not ispipe:
                            raise

                self.current_inode = inode

                while True:
                    changed = self.has_changed()
                    for line in self.read_to_end(f):
                        logging.debug('Got line: %s', line)
                        yield line
                    if changed:
                        break
                    time.sleep(self.pollint)
        except (IOError, OSError) as e:
            if e.errno != errno.ENOENT:
                raise

    def tail(self):
        while True:
            for line in self.tail1():
                yield line
            time.sleep(self.pollint)

    def __iter__(self):
        return self.tail()


def default_message_cb(msg, match):
    print('MESSAGE: %s' % msg)


def default_log_start_f(line):
    return (not line.startswith(' '), None)


class LogParser(object):

    def __init__(self, filename, message_cb=default_message_cb,
                 log_start_f=default_log_start_f, pollint=2, block=True):
        self.tail = PyTail(filename, pollint, block)
        self.message_cb = message_cb
        self.log_start_f = log_start_f
        self.current = None
        self.next = None
        self.current_match = None
        self.next_match = None

    def parse(self):
        self.current = self.__next__
        self.next = None

        for line in self.tail:
            if self.got_line(line):
                self.message_cb(self.current, self.current_match)
                self.current = self.__next__
                self.current_match = self.next_match
                self.next = None

    def got_line(self, line):
        if line is None and self.current is not None:
            return True

        m, match = self.log_start_f(line)
        if m:
            if self.current is None:
                self.current = line
                self.current_match = match
                return False
            else:
                self.next = line
                self.next_match = match
                return True
        else:
            if self.current is not None:
                self.current += line
            # Else we must have started in the middle of a message- ignore
            return False
