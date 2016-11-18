#!/usr/bin/env python2
"""The command line interface"""
import sys
import argparse

from twisted.internet import endpoints, reactor
from twisted.python import log

from .ramdb import RamDatabase
from .dbmdb import DbmDatabase
from .dirdb import DirdbmDatabase
from . import router, data, dbproto, cmdclient, txclient

DATABASES = {  # name -> Database
    "ram": RamDatabase,
    "dbm": DbmDatabase,
    "dir": DirdbmDatabase,
}


def run(args=None):
    """runs the command line interface."""
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Key/Value Network Database")
    parser.add_argument(
        "mode", choices=["router", "cmd"] + DATABASES.keys(), action="store",
        help="What mode the server should operate in",
        )
    parser.add_argument(
        "host", default="0.0.0.0", action="store", nargs="?",
        help="host to serve on/connect to",
        )
    parser.add_argument(
        "port", default=data.DEFAULT_PORT, action="store", type=int, nargs="?",
        help="port to serve on/connect to",
        )
    parser.add_argument(
        "-t", "--type", required=False, default="tcp", action="store", dest="type", nargs="?",
        choices=("tcp", "tcp6", "tls"),
        help="endpoint type to use",
        )
    parser.add_argument(
        "-e", "--endpoint", required=False, default=None, action="store", dest="endpoint",
        help="Use this endpoint instead of creating one from the other arguments",
        )
    parser.add_argument(
        "-p", "--password", action="store", required=False, default=None, dest="password",
        help="password for the server",
        )
    parser.add_argument(
        "-v", "--verbose", action="store_true", dest="verbose", help="print more messages.",
        )
    parser.add_argument(
        "-l", "--logfile", action="store", required=False, dest="logfile", default=None,
        help="file to log to [default: stdout]",
        )
    parser.add_argument(
        "-r", "--reset", action="store_true", required=False, dest="reset",
        help="Reset database and load db from server",
        )
    parser.add_argument(
        "--reset-sleep", action="store", required=False, type=float, default=0.2, dest="sleep_interval",
        help="wait every 128 requests this many seconds before sending the next requests.",
        )
    parser.add_argument(
        "arguments", action="store", nargs="*",
        help="arguments to pass to database interface",
        )
    ns = parser.parse_args(args)

    if ns.verbose:
        if ns.logfile is None:
            log.startLogging(sys.stdout)
        else:
            logfile = open(ns.logfile, "w")
            log.startLogging(logfile)

    if ns.mode == "router":
        if ns.endpoint is None:
            es = "{type}:port={port}:interface={host}".format(type=ns.type, port=ns.port, host=ns.host)
        else:
            es = ns.endpoint
        factory = router.RouterFactory(reactor, ns.password)
        endpoint = endpoints.serverFromString(reactor, es)
        endpoint.listen(factory)
    else:
        if ns.endpoint is None:
            es = "{type}:host={host}:port={port}".format(type=ns.type, port=ns.port, host=ns.host)
        else:
            es = ns.endpoint
        endpoint = endpoints.clientFromString(reactor, es)
        if ns.mode == "cmd":
            cmd = cmdclient.KVNDBCmdClient(reactor)
            protocol = txclient.ClientProtocol(ns.password)
            protocol.callback.addCallback(cmd.defer_entry)
        else:
            db = DATABASES[ns.mode](ns.arguments)
            protocol = dbproto.DatabaseClientProtocol(db, ns.password, reactor, reset=ns.reset, reset_sleep_interval=ns.sleep_interval)
        endpoints.connectProtocol(endpoint, protocol)
    reactor.run()


if __name__ == "__main__":
    run(sys.argv[1:])
