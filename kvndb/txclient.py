"""asynchronous clientside protocol for twisted."""
import struct

from twisted.protocols.basic import IntNStringReceiver
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.python import log

from . import data, utils


class VersionMismatch(Exception):
    """Version does not match"""
    pass


class ProtocolError(Exception):
    """invalid answer/message"""
    pass


class IncorrectPassword(ValueError):
    """Invalid password."""
    pass


class ClientProtocol(IntNStringReceiver):
    """
This protocol connects to the router.
You can use the 'callback' attribute to get a deferred which will be called once the handshake is finished.
"""
    def __init__(self, password):
        if hasattr(IntNStringReceiver, "__init__"):
            IntNStringReceiver.__init__(self)
        self.password = password
        self.requests = {}
        self.free = set()
        self.range_start = None
        self.range_end = None
        self.mode = data.MODE_CONNECTING
        self.structFormat = data.MESSAGE_LENGTH_FORMAT
        self.prefixLength = data.MESSAGE_LENGTH_SIZE
        self.callback = Deferred()  # will be called once the handshake is finished

    def connectionMade(self):
        """called when the connection was established."""
        if hasattr(IntNStringReceiver, "connectionMade"):
            IntNStringReceiver.connectionMade(self)
        # init handshake
        log.msg("Connection established, initiating handshake...")
        self.mode = data.MODE_VERSION
        self.sendString(struct.pack(data.VERSION_FORMAT, data.VERSION))

    def stringReceived(self, msg):
        """called when a message was received."""
        if self.mode == data.MODE_ERROR:
            # error occured, connection is probably already being terminated.
            log.err("Received a message, but the protocol is already mismatching. Ignoring Message.")
            pass

        elif self.mode == data.MODE_VERSION:
            # check version answer
            if msg == data.STATE_OK:
                # Version OK, continue
                log.msg("Version OK, sending mode and requesting range...")
                self.sendString(data.MODE_CLIENT)
                self.mode = data.MODE_RANGE
            elif msg == data.STATE_ERROR:
                # Version mismatch
                log.err("Version is not supported by the server. Losing Connection...")
                self.mode = data.MODE_ERROR
                f = Failure(VersionMismatch("Version does not match!"))
                try:
                    self.transport.loseConnection()
                except:
                    pass
                finally:
                    self.callback.errback(f)
            elif msg == data.STATE_PASSWORD_REQUIRED:
                # Version OK, but password required
                if self.password is not None:
                    log.msg("Version OK, sending password...")
                    self.sendString(self.password)
                    self.mode = data.MODE_PASSWORD
                else:
                    log.err("Version OK, but a password is required!")
                    self.mode = data.MODE_ERROR
                    self.transport.loseConnection()
                    self.callback.errback(Failure(IncorrectPassword("Password required, but None specified!")))
            else:
                # unknown answer
                log.err("Received unknown answer! Losing Connection...")
                self.mode = data.MODE_ERROR
                self.callback.errback(Failure(ProtocolError("Unknown Answer during version check!")))
                self.transport.loseConnection()

        elif self.mode == data.MODE_PASSWORD:
            # check answer for password
            if msg == data.STATE_OK:
                # Password OK, continue
                log.msg("Password OK, sending mode and requesting range...")
                self.mode = data.MODE_RANGE
                self.sendString(data.MODE_CLIENT)  # < -- this is correct
            elif msg == data.STATE_ERROR:
                # Password invalid
                log.err("Invalid password!")
                self.mode = data.MODE_ERROR
                self.callback.errback(Failure(IncorrectPassword("Invalid Password!")))
            else:
                # invalid answer
                log.err("Received unknown Answer. Losing Connection...")
                self.mode = data.MODE_ERROR
                self.callback.errback(Failure(ProtocolError("Unknown Answer during password check!")))
                self.transport.loseConnection()

        elif self.mode == data.MODE_RANGE:
            self.range_start, self.range_end = struct.unpack(data.RANGE_FORMAT, msg)
            log.msg("Range is {s} to {e}.".format(s=self.range_start, e=self.range_end))
            self.cur_id = self.range_start
            self.mode = data.MODE_CLIENT
            self.callback.callback(self)

        elif self.mode == data.MODE_CLIENT:
            # handle answers
            actionbyte = msg[0]
            msg = msg[1:]
            if actionbyte in (data.ID_ALLKEYS, data.ID_ANSWER, data.ID_NOTFOUND):
                rids = msg[:data.MESSAGE_ID_SIZE]
                rid = struct.unpack(data.MESSAGE_ID_FORMAT, rids)[0]
                self.free.add(rid)
                if rid not in self.requests:
                    pass
                else:
                    d = self.requests[rid]
                    del self.requests[rid]
                    if actionbyte == data.ID_ANSWER:
                        value = msg[data.MESSAGE_ID_SIZE:]
                        d.callback(value)
                    elif actionbyte == data.ID_NOTFOUND:
                        f = Failure(KeyError("Key not found!"))
                        d.errback(f)
                    elif actionbyte == data.ID_ALLKEYS:
                        keystring = msg[data.MESSAGE_ID_SIZE:]
                        keylist = utils.keystring2list(keystring)
                        d.callback(keylist)
                    else:
                        log.err("Logic Error! Expected all answer IDs to have been checked!")
            else:
                log.err("Error: Unexpected Answer from server! Losing Connection...")
                self.mode = data.MODE_ERROR
                self.transport.loseConnection()
                self.callback.errback(Failure(ProtocolError("Unknown Answer!")))

        else:
            log.err("Logic Error: set protocol to unknown mode!")

    def get_id(self):
        """returns a request id."""
        if len(self.free) > 0:
            return self.free.pop()
        else:
            i = self.cur_id
            if self.cur_id + 1 >= self.range_end:
                raise RuntimeError("No ids left.")
            self.cur_id += 1
            return i

    def get(self, key):
        """returns a deferred which will be fired with the value of key."""
        assert isinstance(key, str), "Expected key to be a string!"
        d = Deferred()
        rid = self.get_id()
        rids = struct.pack(data.MESSAGE_ID_FORMAT, rid)
        self.requests[rid] = d
        self.sendString(data.ID_GET + rids + key)
        return d

    def set(self, key, value):
        """sets key to value."""
        assert isinstance(key, str) and isinstance(value, str), "Expected key/value to be strings!"
        keylength = len(key)
        keylengthstring = struct.pack(data.MESSAGE_KEY_LENGTH_FORMAT, keylength)
        self.sendString(data.ID_SET + keylengthstring + key + value)

    def delete(self, key):
        """deletes the value for key and key."""
        assert isinstance(key, str), "Expected key to be a string!"
        self.sendString(data.ID_DEL + key)

    def getkeys(self):
        """returns a deferred which will be fired with a list of all keys"""
        d = Deferred()
        rid = self.get_id()
        rids = struct.pack(data.MESSAGE_ID_FORMAT, rid)
        self.requests[rid] = d
        self.sendString(data.ID_GETKEYS + rids)
        return d
