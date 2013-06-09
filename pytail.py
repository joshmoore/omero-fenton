import errno
import os
import time



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
        for line in f.readlines():
            yield line
            self.count += 1

        if not self.block:
            yield None

    def has_changed(self):
        return os.stat(self.filename).st_ino != self.current_inode

    def tail1(self):
        try:
            with open(self.filename) as f:
                inode = os.fstat(f.fileno()).st_ino
                if self.current_inode is None:
                    f.seek(0, 2)
                self.current_inode = inode

                while True:
                    changed = self.has_changed()
                    for line in self.read_to_end(f):
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



def default_message_cb(m):
    print 'MESSAGE: %s' % m

def default_log_start_f(line):
    return not line.startswith(' ')

class LogParser(object):

    def __init__(self, filename, message_cb=default_message_cb,
                 log_start_f=default_log_start_f):
        self.tail = PyTail(filename, 2)
        self.message_cb = message_cb
        self.log_start_f = log_start_f
        self.current = None
        self.next = None

    def parse(self):
        self.current = self.next
        self.next = None

        for line in self.tail:
            if self.got_line(line):
                self.message_cb(self.current)
                self.current = self.next
                self.next = None

    def got_line(self, line):
        if line is None and self.current is not None:
            return True

        if self.log_start_f(line):
            if self.current is None:
                self.current = line
                return False
            else:
                self.next = line
                return True
        else:
            if self.current is not None:
                self.current += line
            # Else we must have started in the middle of a message- ignore
            return False


