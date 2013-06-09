import errno
import os
import time


def default_cb(count, line):
    print count, line

class PyTail(object):
    """
    A polling version of the unix 'tail -F' command
    """

    def __init__(self, filename, cb=None, pollint=0.5):
        self.filename = filename
        if cb:
            self.cb = cb
        else:
            self.cb = default_cb
        self.pollint = pollint
        self.count = 0
        self.current_inode = None

    def read_to_end(self, f):
        for line in f.readlines():
            self.cb(self.count, line)
            self.count += 1
        return f.tell()

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
                    self.read_to_end(f)
                    if changed:
                        break
                    time.sleep(0.5)
        except (IOError, OSError) as e:
            if e.errno != errno.ENOENT:
                raise

    def tail(self):
        while True:
            self.tail1()
            time.sleep(0.5)


