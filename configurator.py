#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import argparse
import ConfigParser


maincfgname = 'arsebot'

def configure():
    # Setup the command line arguments.
    parser = argparse.ArgumentParser('Omero ARSE configuration')

    # Output verbosity options.
    parser.add_argument('-q', '--quiet', help='set logging to ERROR',
                        action='store_const', dest='loglevel',
                        const=logging.ERROR, default=logging.INFO)
    parser.add_argument('-d', '--debug', help='set logging to DEBUG',
                        action='store_const', dest='loglevel',
                        const=logging.DEBUG, default=logging.INFO)

    # Configuration file
    parser.add_argument('-f', '--config', help='Configuration file',
                        dest='config', required=True)
    args = parser.parse_args()

    config = ConfigParser.SafeConfigParser()
    config.optionxform = str
    if not config.read(args.config):
        raise Exception('Invalid configuration file: %s' % args.config)

    mainreq = ['jid', 'password', 'room', 'nick', 'levels']
    maincfg = dict(config.items(maincfgname))
    if any(k not in maincfg for k in mainreq):
        raise Exception('[%s] must contain keys: %s' % (maincfgname, mainreq))

    logcfgs = {}
    for s in sorted(config.sections()):
        if s == maincfgname:
            continue

        try:
            logtype, logname = s.split(' ', 1)
        except ValueError:
            raise Exception('[%s] must be in the form [logtype name]', s)

        if logtype not in logcfgs:
            logcfgs[logtype] = []
        d = dict(config.items(s))
        d['name'] = logname
        logcfgs[logtype].append(d)

    return args, maincfg, logcfgs


def getcfgkey(key, *cfgs, **kwargs):
    value = None
    for cfg in cfgs:
        if key in cfg:
            value = cfg[key]
            if 'cast' in kwargs:
                value = kwargs['cast'](value)
            break
    logging.debug('%s=%s', key, value)
    return value

