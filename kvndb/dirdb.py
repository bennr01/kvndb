"""dirdbm database interface."""
from twisted.persisted import dirdbm


class DirdbmDatabase(object):
    """A dirdbm database"""
    def __init__(self, args):
        self.args = args
        if len(self.args) != 1:
            raise ValueError, "Expected exactly one argument for the DB."
        self.path = args[0]
        self.db = dirdbm.DirDBM(self.path)

    def get(self, key):
        """returns the value for key."""
        if key in self.db:
            return self.db[key]
        else:
            raise KeyError(key)

    def set(self, key, value):
        """sets key to value"""
        self.db[key] = value

    def delete(self, key):
        """deletes the key/value pair for key."""
        try:
            del self.db[key]
        except KeyError:
            pass

    def getkeys(self):
        """returns a list of keys."""
        return self.db.keys()

    def reset(self):
        """resets the database."""
        self.db.clear()

    def close(self):
        """this should close the database."""
        self.db.close()  # this is no-op
