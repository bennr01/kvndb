"""A in memory database."""


class RamDatabase(object):
    """A database living in the memory"""
    def __init__(self, args):
        self.args = args
        self.db = {}

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
        self.db = {}

    def close(self):
        """no-op."""
        pass
