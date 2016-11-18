"""constants and other definitions"""
import struct

ID_GET = "\x01"
ID_SET = "\x02"
ID_DEL = "\x03"
ID_GETKEYS = "\x04"
ID_ANSWER = "\x05"
ID_NOTFOUND = "\x06"
ID_ALLKEYS = "\x07"
ID_SWITCH = "\x08"

VERSION = 1
VERSION_FORMAT = "!Q"
VERSION_LENGTH = struct.calcsize(VERSION_FORMAT)

MODE_VERSION = "\x01"
MODE_PASSWORD = "\x02"
MODE_UNKNOWN = "\x03"
MODE_SERVER = "\x04"
MODE_CLIENT = "\x05"
MODE_ERROR = "\x06"
MODE_CONNECTING = "\x07"
MODE_RANGE = "\x08"

STATE_OK = "O"
STATE_ERROR = "E"
STATE_PASSWORD_REQUIRED = "P"

MESSAGE_LENGTH_FORMAT = "!Q"
MESSAGE_LENGTH_SIZE = struct.calcsize(MESSAGE_LENGTH_FORMAT)
MESSAGE_KEY_LENGTH_FORMAT = "!L"
MESSAGE_KEY_LENGTH_SIZE = struct.calcsize(MESSAGE_KEY_LENGTH_FORMAT)
MESSAGE_ID_FORMAT = "!I"
MESSAGE_ID_SIZE = struct.calcsize(MESSAGE_ID_FORMAT)

DEFAULT_PORT = 54565

INVALID_PASSWORD_SLEEP_INTERVAL = 3

RANGE = 2**20
RANGE_FORMAT = "!QQ"
RANGE_SIZE = struct.calcsize(RANGE_FORMAT)
