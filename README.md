#KVNDB - A Key-Value Network Database
KVNDB is a simple scalable pure-python key/value database and a client-API.

#Features
- Scalable
- Password protection (optional)
- stores key/value pairs (both needs to be strings)
- pure-python
- asynchronous
- command-line script included
- allows to automatically reset a database and then sync with the other databases
- different database-interfaces included

#Concept
A KVNDB consists of three components:

   1. **The Router** is the central manager, which handles all connections and splits the requests.
        He also handles the version and password checks.
        
   2. **The Databases** connect to the router and provide the databases.
        Every database receive all `set` and `del` commands, but the `get` and `getkeys` commands are randomly splitted.
        
   3. **The Clients** connect to the router and send requests.


#Usage

**using `kvndb`:**

   KVNDB includes the `kvndb` script, which will automatically be added to your PATH when the setup is run.
   Command: `kvndb [args]`

**Using `python`:**

   You can run KVNDB directly as a standalone module using python.
   Command: `python - m kvndb [args]`
**Using as a module:**

   You can also import `kvndb` for a more flexible setup.
   
   **Modules:**

   `kvndb.router`: The router module. The router class is available as `kvndb.router.RouterFactory`.

   `kvndb.dbproto`: The code gluing a database and the router togeter. You can access the protocol as `kvndb.dbproto.DatabaseClientProtocol`.

   `kvndb.txclient`: The KVNDB client for twisted. You can access the client protocal as `kvndb.txclient.ClientProtocol`.

   `kvndb.runner`: The command line interface. You can pass some arguments to `kvndb.runner.run` to parse and run them.

   `kvndb.cmdclient`: The command line console. You can subclass `kvndb.cmdclient.KVNDBCmdClient` to extend the command line.

   `kvndb.data`: Some constants and other data.

**Arguments:**

You can pass the following arguments to `kvndb`/`python -m kvndb`:

   `host`: [ALL] when constructing the endpoint, use this as the host. Default: `0.0.0.0`.

   `port`: [ALL] when constructing the endpoint, use this as the port. Default: `54565`.

   `1`: [ALL] What mode/database to use. Special modes are `router`(starts the router) and `cmd`(launch a console).

   `arguments ARGS`: [DATABASES] pass theses arguments to the database-interface.

   `--help`: [ALL] show a help message.

   `-t T`; `--type T`: [ALL] endpoint type to use. This may be either `tcp`, `tcp6` or `tls`. For more options, use the `-e` option.

   `-e E`; `--endpoint E`: [ALL] use the following string to construct a twisted endpoint. Ignore other arguments which would define an endpoint.

   `-p P`; `--password P`: [ALL] When running as a router, set this password as the password. Otherwise, send this password if required.

   `-v`; `--verbose`: [ALL] Enable verbose output.

   `-l F`; `--logfile F`: [ALL] Log to this file. Requires `-v` to be set.

   `-r`: `--reset`: [DATABASES] After connecting to the router, delete all keys from the database and the sync from the other databases connected to the router.
    
    

#Requirements
- python2.7
- twisted

#Installation

**Using `pip`:**

Once this module is available on pypi, you can install it using `pip install kvndb`.

**From source:**

1. Download/clone this repository

2. Install requirements

3. Run `python setup.py install` inside this directory. This may require root access.

#License

MIT


**Author**: Benjamin Vogt

**Project homepage:** https://github.com/bennr01/kvndb/
