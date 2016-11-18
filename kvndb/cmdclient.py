"""Command line client interface."""
import cmd
import shlex

from twisted.internet import threads

from . import data, utils


class KVNDBCmdClient(cmd.Cmd):
    """A command line interface for a KVNDB client."""
    
    prompt = "(?)"
    intro = "KVNDB Cmd-Client Protocol v{v}\nType 'help' for help.".format(v=data.VERSION)

    def __init__(self, reactor, *args, **kwargs):
        cmd.Cmd.__init__(self, *args, **kwargs)
        self.reactor = reactor
        self.proto = None

    def do_set(self, cmd):
        """set KEY VALUE: set KEY to VALUE."""
        args = shlex.split(cmd)
        if len(args) != 2:
            self.stdout.write("Error: Expected 2 arguments, got {n} instead!\n".format(n=len(args)))
            return
        else:
            key, value = args
            self.reactor.callFromThread(self.proto.set, key, value)

    def do_del(self, cmd):
        """del KEY: delete KEY"""
        self.reactor.callFromThread(self.proto.delete, cmd)

    do_delete = do_remove = do_del

    def do_get(self, cmd):
        """get KEY: show the value of KEY"""
        key = cmd
        try:
            value = threads.blockingCallFromThread(
                self.reactor, self.proto.get, key,
                )
        except KeyError:
            self.stdout.write("Error: Key '{k}' not found!\n".format(k=key))
            return
        except Exception as e:
            self.stdout.write("Error: {e}\n".format(e=e))
            return
        else:
            self.stdout.write("{v}\n".format(v=value))

    do_show = do_view = do_print = do_get

    def do_getkeys(self, cmd):
        """getkeys [COLUMNS]: show a list of all keys."""
        if cmd:
            try:
                cols = int(cmd)
            except ValueError:
                self.stdout.write("Error: Invalid argument!\n")
                return
        else:
            cols = 2
        try:
            keys = threads.blockingCallFromThread(
                self.reactor, self.proto.getkeys,
                )
        except Exception as e:
            self.stdout.write("Error: {e}\n".format(e=e))
            return
        else:
            sk = sorted(keys)
            formated = utils.fmtcols(sk, cols)
            if not formated.endswith("\n"):
                formated += "\n"
            self.stdout.write(formated)

    do_keys = do_list = do_getkeys

    def defer_entry(self, proto):
        """
this is a utility function which should be used by the ClientProtocol.
When called, the protocol will be set and the REPL-starts.
"""
        self.proto = proto
        self.reactor.callInThread(self.cmdloop)

    def do_EOF(self, cmd=""):
        """EOF: quit the command loop."""
        self.reactor.callFromThread(self.reactor.stop)
        return True

    do_quit = do_exit = do_EOF

    def postcmd(self, stop, line):
        """called after a line has been executed."""
        return stop
