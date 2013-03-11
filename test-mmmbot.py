#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from mmmbot import MmmBot


class MmmBotTestWrapper(MmmBot):
    class Message:
        class Bare:
            def __init__():
                self.bare = 'Message from'

        def __init__(self, nick, body):
            self['mucnick'] = nick
            self['body'] = body
            self['from'] = Bare()

    def __init__(self):
        MmmBot.__init__(self, None, None, None, None)
        self.messages = []

    def send_message(self, mto, mbody, mtype):
        self.messages.append((mto, mbody, mtype))



class TestMmmBot(unittest.TestCase):

    def create_bot(self):
        bot = MmmBotTestWrapper()
        return bot

    def create_message(self, body, nick = 'User'): 
        class Bare:
            def __init__(self):
                self.bare = 'Message from'

        msg = {'mucnick': nick, 'body': body, 'from': Bare()}
        return msg


    def test_fuzzy_greeting(self):
        b = self.create_bot()

        r = b.fuzzy_greeting('M-o-R-n-I-n-G', 'User')
        self.assertEqual(r, 'morning User')

        r = b.fuzzy_greeting('Helllllooooooooo\nAll', 'User')
        self.assertEqual(r, 'hello User')

        r = b.fuzzy_greeting('Helllllooooooooo Someone', 'User')
        self.assertIsNone(r)


    def test_exact_greeting(self):
        b = self.create_bot()

        r = b.exact_greeting('Dobrý Večer', 'User')
        self.assertEqual(r, 'dobrý večer User')

        r = b.exact_greeting('καλό απόγευμα', 'User')
        self.assertEqual(r, 'καλό απόγευμα User')

        r = b.exact_greeting('aloha\na', 'User')
        self.assertIsNone(r)


    def test_beer(self):
        b = self.create_bot()

        r = b.beer('Do you want a beer?', 'User')
        self.assertEqual(r, u'%botsnack be\u202ere')

        r = b.beer('beera', 'User')
        self.assertIsNone(r)



    def test_muc_message(self):
        b = self.create_bot()
        msg = self.create_message('>>>>> Gooooooood moooooorning everyone!!!')
        b.muc_message(msg)
        self.assertEqual(b.messages,
                         [('Message from', 'morning User', 'groupchat')])

        b = self.create_bot()
        msg = self.create_message('>>>>> こんにちは!!!')
        b.muc_message(msg)
        self.assertEqual(b.messages,
                         [('Message from', 'こんにちは User', 'groupchat')])

        b = self.create_bot()
        msg = self.create_message('morning', 'test-bot0')
        b.muc_message(msg)
        self.assertEqual(b.messages, [])






