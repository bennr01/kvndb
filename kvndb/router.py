"""The KVNDB Router coordinates the databases and requestss"""
import struct
import random


from twisted.internet.protocol import Factory
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.python.failure import Failure
from twisted.python import log
from twisted.protocols.basic import IntNStringReceiver

from . import data, utils


class RouterFactory(Factory):
    """A twisted.internet.protocol.Factory for the request routing."""
    def __init__(self, reactor, pswd):
        if hasattr(Factory, "__init__"):
            # call __init__ if required
            Factory.__init__(self)
        self.reactor = reactor
        self.pswd = pswd
        self.servers = []
        self.syncing = []
        self.all = []
        self.free_ranges = []
        self.calls = {}

    def buildProtocol(self, addr):
        """builds the protocol."""
        log.msg("Building protocol for connection with client '{a}'...".format(a=addr))
        return RouterProtocol(self)

    def got_answer(self, proto, actionbyte, msg):
        """a server answered a request."""
        rid = struct.unpack(data.MESSAGE_ID_FORMAT, msg[:data.MESSAGE_ID_SIZE])[0]
        if rid not in self.calls:
            # request already answered by another server
            return
        elif actionbyte == data.ID_ANSWER:
            value = msg[data.MESSAGE_ID_SIZE:]
            d = self.calls[rid]
            try:
                d.callback(value)
            finally:
                del self.calls[rid]
        elif actionbyte == data.ID_NOTFOUND:
            d = self.calls[rid]
            fail = Failure(KeyError())
            try:
                d.errback(fail)
            finally:
                del self.calls[rid]
        elif actionbyte == data.ID_ALLKEYS:
            keylist = msg[data.MESSAGE_ID_SIZE:]
            d = self.calls[rid]
            try:
                d.callback(keylist)
            finally:
                del self.calls[rid]
        else:
            raise RuntimeError("Invalid Answer!")

    def get(self, request_id, key):
        """returns the value for key."""
        rid = struct.unpack(data.MESSAGE_ID_FORMAT, request_id)[0]
        d = Deferred()
        if len(self.servers) == 0:
            # no server available; raise KeyError to deferred
            f = Failure(KeyError())
            d.errback(f)
            return d
        self.calls[rid] = d
        server = random.choice(self.servers)
        server.send_get(request_id, key)
        return d

    def set(self, key, value):
        """sets the value for key."""
        for server in self.servers + self.syncing:
            server.send_set(key, value)

    def delete(self, key):
        """deletes the value for key."""
        for server in self.servers + self.syncing:
            server.send_del(key)

    def getkeys(self, request_id,):
        """returns a list of keys."""
        if len(self.servers) == 0:
            # no servers, but client expects sync
            keys = []  # because there are no databases connected.
            answer = utils.keylist2string(keys)
            return answer
        server = random.choice(self.servers)
        rid = struct.unpack(data.MESSAGE_ID_FORMAT, request_id)[0]
        d = Deferred()
        self.calls[rid] = d
        server.send_getkeys(request_id)
        return d

    def get_range(self):
        """returns a rid range for a client."""
        i = 0
        while True:
            start = data.RANGE * i
            end = start + data.RANGE
            found = True
            for client in self.all:
                cs = client.range_start
                if cs == start:
                    found = False
                    break
            if found:
                return (start, end)
            i += 1


class RouterProtocol(IntNStringReceiver):
    """A twisted.internet.protocol.Protocol for the request routing."""
    def __init__(self, factory):
        if hasattr(IntNStringReceiver, "__init__"):
            IntNStringReceiver.__init__(self)
        self.factory = factory
        self.structFormat = data.MESSAGE_LENGTH_FORMAT
        self.prefixLength = data.MESSAGE_LENGTH_SIZE
        self.mode = data.MODE_CONNECTING
        self.can_switch = False
        self.range_start = None
        self.range_end = None

    def connectionMade(self):
        """called when the connection was established."""
        if hasattr(IntNStringReceiver, "connectionMade"):
            IntNStringReceiver.connectionMade(self)
        self.mode = data.MODE_VERSION
        log.msg("Starting Handshake...")

    @inlineCallbacks
    def stringReceived(self, msg):
        """called when a string was received."""
        if self.mode == data.MODE_VERSION:
            # check version
            if len(msg) != data.VERSION_LENGTH:
                log.err("Got invalid version string from client. Aborting connection...")
                # protocol violation
                self.transport.abortConnection()
            version = struct.unpack(data.VERSION_FORMAT, msg)[0]
            if version != data.VERSION:
                # version mismatch
                log.msg("Client uses an unsupported version. Losing connection...")
                self.sendString(data.STATE_ERROR)
                self.transport.loseConnection()
                self.mode = data.MODE_ERROR
            else:
                # proceed with password handling if required
                if self.factory.pswd is not None:
                    log.msg("Version OK, asking for password...")
                    self.sendString(data.STATE_PASSWORD_REQUIRED)
                    self.mode = data.MODE_PASSWORD
                else:
                    log.msg("Version OK, asking for mode...")
                    self.sendString(data.STATE_OK)
                    self.mode = data.MODE_UNKNOWN

        elif self.mode == data.MODE_PASSWORD:
            # check password
            if msg != self.factory.pswd:
                # invalid password
                yield utils.dsleep(self.factory.reactor, data.INVALID_PASSWORD_SLEEP_INTERVAL)  # sleep to prevent high speed attacks.
                log.msg("Client sent invalid password. Losing connection...")
                self.sendString(data.STATE_ERROR)
                self.transport.loseConnection()
                self.mode = data.MODE_ERROR
            else:
                # password correct
                log.msg("Password OK, asking for mode...")
                self.sendString(data.STATE_OK)
                self.mode = data.MODE_UNKNOWN

        elif self.mode == data.MODE_UNKNOWN:
            # handle client mode
            if msg == data.MODE_SERVER:
                # client host db
                log.msg("Client identified as a database. Sending range...")
                self.mode = data.MODE_SERVER
                self.factory.servers.append(self)
                self.can_switch = True
            elif msg == data.MODE_CLIENT:
                # client wants to access database
                log.msg("Client identified as a client. Sending range...")
                self.mode = data.MODE_CLIENT
                self.can_switch = False
            else:
                # protocol violation
                log.err("Client sent invalid mode. Aborting connection...")
                self.transport.abortConnection()

            # now set rid range start and send int
            self.range_start, self.range_end = self.factory.get_range()
            rangestring = struct.pack(data.RANGE_FORMAT, self.range_start, self.range_end)
            self.sendString(rangestring)
            self.factory.all.append(self)

        elif self.mode == data.MODE_SERVER:
            # message from the server
            actionbyte = msg[0]
            if actionbyte in (data.ID_ANSWER, data.ID_NOTFOUND, data.ID_ALLKEYS):
                self.factory.got_answer(self, actionbyte, msg[1:])
            elif actionbyte == data.ID_SWITCH:
                self.switch_mode()

        elif self.mode == data.MODE_CLIENT:
            # request from client
            actionbyte = msg[0]
            if actionbyte == data.ID_SET:
                # set
                keysize = struct.unpack(data.MESSAGE_KEY_LENGTH_FORMAT, msg[1:1 + data.MESSAGE_KEY_LENGTH_SIZE])[0]
                key = msg[1 + data.MESSAGE_KEY_LENGTH_SIZE:1 + data.MESSAGE_KEY_LENGTH_SIZE + keysize]
                value = msg[1 + data.MESSAGE_KEY_LENGTH_SIZE + keysize:]
                self.factory.set(key, value)
            elif actionbyte == data.ID_GET:
                # get
                request_id = msg[1:1 + data.MESSAGE_ID_SIZE]
                key = msg[1 + data.MESSAGE_ID_SIZE:]
                try:
                    value = yield self.factory.get(request_id, key)
                    self.sendString(data.ID_ANSWER + request_id + value)
                except KeyError:
                    self.sendString(data.ID_NOTFOUND + request_id)
            elif actionbyte == data.ID_DEL:
                # del
                key = msg[1:]
                self.factory.delete(key)
            elif actionbyte == data.ID_GETKEYS:
                rid = msg[1:]
                keystring = yield self.factory.getkeys(rid)
                self.sendString(data.ID_ALLKEYS + rid + keystring)
            elif actionbyte == data.ID_SWITCH:
                self.switch_mode()

        else:
            # unknown mode; server side error
            raise RuntimeError("Invalid Mode")

    def connectionLost(self, reason):
        """called when the connection was lost."""
        log.msg("Connection lost. Reason: {r}".format(r=reason))
        if self in self.factory.servers:
            self.factory.servers.remove(self)
        if self in self.factory.syncing:
            self.factory.syncing.remove(self)

        if self in self.factory.all:
            self.factory.all.remove(self)

    def send_get(self, rid, key):
        """if in server mode, request the value for key from the db-server. otherwise, raise AssertionError"""
        assert self.mode == data.MODE_SERVER, "This protocol is not connected to a database!"
        self.sendString(data.ID_GET + rid + key)

    def send_set(self, key, value):
        """if in server mode, tell the db-server to set key to value. otherwise, raise AssertionError"""
        assert self.mode == data.MODE_SERVER or self.can_switch, "This protocol is not connected to a database!"
        keylength = struct.pack(data.MESSAGE_KEY_LENGTH_FORMAT, len(key))
        self.sendString(data.ID_SET + keylength + key + value)

    def send_del(self, key):
        """if in server mode, tell the db-server to delete the value for key. otherwise, raise AssertionError"""
        assert self.mode == data.MODE_SERVER or self.can_switch, "This protocol is not connected to a database!"
        self.sendString(data.ID_DEL + key)

    def send_getkeys(self, rid):
        """if in server mode, requests a list of keys from the db-server. otherwise, raise AssertionError"""
        assert self.mode == data.MODE_SERVER, "This protocol is not connected to a database!"
        self.sendString(data.ID_GETKEYS + rid)

    def switch_mode(self):
        """switch between client/server mode."""
        if self.can_switch:
            if self.mode == data.MODE_SERVER:
                if self in self.factory.servers:
                    self.factory.servers.remove(self)
                if self not in self.factory.syncing:
                    self.factory.syncing.append(self)
                self.mode = data.MODE_CLIENT
            elif self.mode == data.MODE_CLIENT:
                if self not in self.factory.servers:
                    self.factory.servers.append(self)
                if self in self.factory.syncing:
                    self.factory.syncing.remove(self)
                self.mode = data.MODE_SERVER

    # DEBUG FUNCTIONS
    """
    def sendString(self, s):
        print "sending: {s}".format(s=repr(s))
        IntNStringReceiver.sendString(self, s)
    """
