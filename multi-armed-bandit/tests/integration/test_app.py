import json
import logging
import unittest

from chalice.config import Config
from chalice.local import LocalGateway

from app import app

class TestApp(unittest.TestCase):
    def setUp(self):
        self.gateway = LocalGateway(app, Config())

    def test_contains_all(self):
        states = ["PAGE_1", "PAGE_2", "PAGE_3", "PAGE_4", "PAGE_5"]
        body = {"states": states}
        response = self.gateway.handle_request(method='POST',
                                               path='/order',
                                               headers={
                                                  'Content-Type': 'application/json'
                                               },
                                               body=json.dumps(body))
        logging.info(response)
        body = json.loads(response['body'])
        assert response['statusCode'] == 200
        for state in states:
            assert state in body['order']

    def test_reward(self):
        body = {"state": "PAGE_3",
                "reward": 700}
        response = self.gateway.handle_request(method='POST',
                                               path='/metric',
                                               headers={
                                                  'Content-Type': 'application/json'
                                               },
                                               body=json.dumps(body))
        body = json.loads(response['body'])
        assert response['statusCode'] == 200

if __name__ == '__main__':
    unittest.main()