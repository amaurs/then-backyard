import json
import logging
import unittest

from chalice.config import Config
from chalice.local import LocalGateway

from app import app

class TestApp(unittest.TestCase):
    def setUp(self):
        self.gateway = LocalGateway(app, Config())

    def test_dummy(self):
        assert False


if __name__ == '__main__':
    unittest.main()