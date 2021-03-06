from . import BaseTest

import unittest
import mock

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser

from stored_messages.backends.exceptions import MessageTypeNotSupported, MessageDoesNotExist
from stored_messages.backends.redis import RedisBackend
from stored_messages.backends.redis.backend import Message

from stored_messages import STORED_ERROR


class RedisMock(object):
    """
    Mock the Redis server instance with Django in-memory cache
    """
    def rpush(self, key, data):
        l = cache.get(key)
        if l is None:
            l = []
        l.append(data)
        cache.set(key, l)

    def lrange(self, key, *args, **kwargs):
        return cache.get(key) or []

    def delete(self, key):
        cache.delete(key)

    def lrem(self, key, count, data):
        l = cache.get(key)
        l.remove(data)
        cache.set(key, l)

    def flushdb(self):
        cache.clear()

    @staticmethod
    def from_url(*args, **kwargs):
        return RedisMock()

    def StrictRedis(self, *args, **kwargs):
        return self


try:
    from stored_messages.backends.redis.backend import redis
    REDISPY_MISSING = False

    if getattr(settings, 'MOCK_REDIS_SERVER', True):
        patcher = mock.patch('stored_messages.backends.redis.backend.redis')
        redis = patcher.start()
        redis.StrictRedis = RedisMock

except ImportError:
    REDISPY_MISSING = True


@unittest.skipIf(REDISPY_MISSING, "redis-py not installed")
class TestRedisBackend(BaseTest):
    def setUp(self):
        super(TestRedisBackend, self).setUp()
        self.client = redis.StrictRedis.from_url(settings.STORED_MESSAGES['REDIS_URL'])
        self.backend = RedisBackend()
        self.backend._flush()
        self.message = self.backend.create_message(STORED_ERROR, 'A message for you')
        self.anon = AnonymousUser()

    def test_inbox_store(self):
        self.backend.inbox_store([self.user], self.message)
        data = self.client.lrange('user:%d:notifications' % self.user.pk, 0, -1).pop()
        self.assertEqual(self.backend._fromJSON(data), self.message)
        self.assertRaises(MessageTypeNotSupported, self.backend.inbox_store, [], {})

    def test_inbox_list(self):
        message = self.backend.create_message(STORED_ERROR, 'Another message for you')
        self.backend.inbox_store([self.user], message)
        self.backend.inbox_store([self.user], self.message)
        messages = self.backend.inbox_list(self.user)
        self.assertEqual(messages[0], message)
        self.assertEqual(messages[1], self.message)
        self.assertEqual(self.backend.inbox_list(self.anon), [])

    def test_inbox_purge(self):
        message = self.backend.create_message(STORED_ERROR, 'Another message for you')
        self.backend.inbox_store([self.user], self.message)
        self.backend.inbox_store([self.user], message)
        self.backend.inbox_purge(self.user)
        self.assertEqual(len(self.backend.inbox_list(self.user)), 0)
        self.backend.inbox_purge(self.anon)

    def test_inbox_delete(self):
        self.backend.inbox_store([self.user], self.message)
        self.backend.inbox_delete(self.user, self.message.id)
        self.assertEqual(len(self.backend.inbox_list(self.user)), 0)
        self.assertRaises(MessageDoesNotExist, self.backend.inbox_delete, self.user, -1)

    def test_archive_store(self):
        self.backend.archive_store([self.user], self.message)
        data = self.client.lrange('user:%d:archive' % self.user.pk, 0, -1).pop()
        self.assertEqual(self.backend._fromJSON(data), self.message)
        self.assertRaises(MessageTypeNotSupported, self.backend.archive_store, [], {})

    def test_archive_list(self):
        message = self.backend.create_message(STORED_ERROR, 'Another message for you')
        self.backend.archive_store([self.user], message)
        self.backend.archive_store([self.user], self.message)
        messages = self.backend.archive_list(self.user)
        self.assertEqual(messages[0], message)
        self.assertEqual(messages[1], self.message)

    def test_create_message(self):
        message = self.backend.create_message(STORED_ERROR, 'Another message for you')
        self.assertIsInstance(message, Message)

    def test_inbox_get(self):
        self.backend.inbox_store([self.user], self.message)
        m = self.backend.inbox_get(self.user, self.message.id)
        self.assertEqual(m, self.message)
        self.assertRaises(MessageDoesNotExist, self.backend.inbox_get, self.user, -1)

    def test_can_handle(self):
        self.assertFalse(self.backend.can_handle({}))
        self.assertTrue(self.backend.can_handle(self.message))
