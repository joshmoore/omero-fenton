omero-fenton
===========

OMERO Adverse Reporting of System Errors
----------------------------------------

This is a jabber bot for monitoring OMERO log files.

Installation
------------

Python module requirements, install these system wide, or into a Virtualenv:

* argparse
* sleekxmpp

Clone this repository:

```
git clone https://github.com/manics/omero-fenton.git
cd omero-fenton
```

Create the configuration file by copying `example.cfg` and editting.

* Enter the Jabber connection details: Jabber ID, password, nickname, conference room.
* Each log file has its own configuration section, section headings should be changed and will be printed alongside log messages.
* `file` should be the path to a log file, for convenience you can just symlink the OMERO logs directory into the current directory.
* Rate limits are applied per file.

Run the bot from the current directory:

```
python OmeroFenton.py -f CONFIGURATION.CFG
```
