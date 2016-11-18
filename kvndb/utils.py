"""utility functions"""
import struct

from twisted.internet.defer import Deferred

from . import data


def keystring2list(s):
    """convert a string of keys to a list of keys."""
    if len(s) == 0:
        return []
    keys = []
    i = 0
    while i < len(s):
        keylength = struct.unpack(data.MESSAGE_KEY_LENGTH_FORMAT, s[i:i + data.MESSAGE_KEY_LENGTH_SIZE])[0]
        i += data.MESSAGE_KEY_LENGTH_SIZE
        key = s[i:i + keylength]
        keys.append(key)
        i += keylength
    return keys


def keylist2string(keys):
    """converts a list of keys to a string."""
    answer = []
    for key in keys:
        keylength = len(key)
        lengthdata = struct.pack(data.MESSAGE_KEY_LENGTH_FORMAT, keylength)
        answer += [lengthdata, str(key)]
    return "".join(answer)


def dsleep(reactor, s):
    """return a deferred, which will be called after s seconds."""
    d = Deferred()
    reactor.callLater(s, d.callback, None)
    return d


def fmtcols(mylist, cols):
    """
formats a list into columns.
Copied from https://stackoverflow.com/questions/171662/formatting-a-list-of-text-into-columns
"""
    lines = ("\t".join(mylist[i:i + cols]) for i in xrange(0, len(mylist), cols))
    return '\n'.join(lines)
