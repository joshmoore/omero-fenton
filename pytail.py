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

