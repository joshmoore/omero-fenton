omero-fenton
===========

OMERO error logs reporting system
---------------------------------

This is a Slack bot for monitoring OMERO log files.

Installation
------------

Requires Python 2.7+. Install the following Python module requirements, either system wide, or into a Virtualenv:

    pip install -r requirements.txt

Clone this repository:

    git clone https://github.com/manics/omero-fenton.git
    cd omero-fenton


Create the configuration file by copying `example.cfg` and editting.

* Create a bot-user and token from https://my.slack.com/services/new/bot
* Enter the Slack connection details: bot-user, Slack token, channel (including `#`).
* Each log file has its own configuration section, section headings should be changed and will be printed alongside log messages.
* `file` should be the path to a log file, for convenience you can just symlink the OMERO logs directory into the current directory.
* Rate limits are applied per file.
* If you want to interact with the bot you must invite the bot-user to the channel, otherwise you will only receive notifications.

Run the bot from the current directory:

```
python OmeroFenton.py -f CONFIGURATION.CFG
```
