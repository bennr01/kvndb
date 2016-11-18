"""Databaseserver side protocol of the routing."""
import struct
import os

from twisted.protocols.basic import IntNStringReceiver
from twisted.internet.defer import Deferred, inlineCallbacks
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


class DatabaseClientProtocol(IntNStringReceiver):
    """This protocol connects a database to the router."""
    def __init__(self, db, password, reactor, reset=False, reset_sleep_interval=0.2):
        if hasattr(IntNStringReceiver, "__init__"):
            IntNStringReceiver.__init__(self)
        self.db = db
        self.reactor = reactor
        self.password = password
        self.reset = reset
        self.sleep_interval = reset_sleep_interval
        self.reset_req_string = os.urandom(data.MESSAGE_ID_SIZE)
        self.to_sync = []
        self.reset_requests = {}
        self.range_start = None
        self.range_end = None
        self.free = set()
        self.cur_id = 0
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

    def connectionLost(self, reason=None):
        """this will be called when the connection was lost."""
        log.err("Error: Connection lost. Reason: {r}".format(r=reason))
        log.msg("Closing database...")
        self.db.close()
        log.msg("Database closed.")

    @inlineCallbacks
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
                self.sendString(data.MODE_SERVER)
                self.mode = data.MODE_RANGE  # <--- this is correct
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
                self.sendString(data.MODE_SERVER)  # <--- this is correct
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
            self.mode = data.MODE_SERVER
            if self.reset:
                self.init_reset()
            else:
                self.callback.callback(self)

        elif self.mode == data.MODE_SERVER:
            # db requests.
            actionbyte = msg[0]
            msg = msg[1:]
            if actionbyte == data.ID_SET:
                keylength = struct.unpack(data.MESSAGE_KEY_LENGTH_FORMAT, msg[:data.MESSAGE_KEY_LENGTH_SIZE])[0]
                key = msg[data.MESSAGE_KEY_LENGTH_SIZE:data.MESSAGE_KEY_LENGTH_SIZE + keylength]
                if self.reset:
                    if key in self.to_sync:
                        self.to_sync.remove(key)
                value = msg[data.MESSAGE_KEY_LENGTH_SIZE + keylength:]
                self.db.set(key, value)
            elif actionbyte == data.ID_GET:
                rid = msg[:data.MESSAGE_ID_SIZE]
                key = msg[data.MESSAGE_ID_SIZE:]
                try:
                    value = yield self.db.get(key)
                except KeyError:
                    self.sendString(data.ID_NOTFOUND + rid)
                else:
                    self.sendString(data.ID_ANSWER + rid + str(value))

            elif actionbyte == data.ID_DEL:
                key = msg
                if key in self.to_sync:
                    self.to_sync.remove(key)
                try:
                    self.db.delete(key)
                except:
                    pass

            elif actionbyte == data.ID_GETKEYS:
                rid = msg
                keys = yield self.db.getkeys()
                answer = utils.keylist2string(keys)
                self.sendString(data.ID_ALLKEYS + rid + answer)

            elif actionbyte == data.ID_ALLKEYS:
                # answer during reset
                rid = msg[:data.MESSAGE_ID_SIZE]
                self.free.add(struct.unpack(data.MESSAGE_ID_FORMAT, rid)[0])
                if rid == self.reset_req_string:
                    log.msg("Received keylist, starting value requests...")
                    keystring = msg[data.MESSAGE_ID_SIZE:]
                    keys = utils.keystring2list(keystring)
                    if len(keys) == 0:
                        log.msg("Keylist empty; skipping value requests...")
                        self.sendString(data.ID_SWITCH)
                        self.callback.callback(self)
                        pass
                    else:
                        # request all values for key
                        self.to_sync = keys
                        del keys  # this list may be big, we should delete it to free some RAM
                        done = 0
                        while True:
                            if len(self.to_sync) == 0:
                                break
                            rid = self.get_id()
                            key = self.to_sync.pop(0)
                            self.reset_requests[rid] = key
                            rids = struct.pack(data.MESSAGE_ID_FORMAT, rid)
                            self.sendString(data.ID_GET + rids + key)
                            if (done % 128) == 0:
                                yield utils.dsleep(self.reactor, self.sleep_interval)
                            done += 1
                        log.msg("Finished sending value requests.")
                else:
                    log.err("Received invalid RID during sync!")

            elif actionbyte == data.ID_ANSWER:
                # request answer during sync
                rids = msg[:data.MESSAGE_ID_SIZE]
                rid = struct.unpack(data.MESSAGE_ID_FORMAT, rids)[0]
                self.free.add(rid)
                value = msg[data.MESSAGE_ID_SIZE:]
                key = self.reset_requests.get(rid, None)
                if key is None:
                    log.err("Received non-requested RID. Ignoring...")
                else:
                    del self.reset_requests[rid]
                    self.db.set(key, value)
                if (len(self.reset_requests) == 0) and (len(self.to_sync) == 0):
                    # this "if" will only be checked if actionybte == data.ID_ANSWER, which can only be sent during a sync
                    log.msg("Finished sync.")
                    self.sendString(data.ID_SWITCH)
                    self.callback.callback(self)

            else:
                # ignore errors here
                pass

        else:
            log.err("Received unknown Answer. Losing Connection...")
            self.mode = data.MODE_ERROR
            self.callback.errback(Failure(ProtocolError("Unknown Answer!")))
            self.transport.loseConnection()

    def init_reset(self):
        """initiates a database reset."""
        log.msg("Initiating database reset...")
        self.db.reset()
        log.msg("Starting sync...")
        self.sendString(data.ID_SWITCH)
        self.sendString(data.ID_GETKEYS + self.reset_req_string)

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
