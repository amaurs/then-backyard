import json
import logging
import unittest

from chalice.config import Config
from chalice.local import LocalGateway

from app import app

class TestApp(unittest.TestCase):
    def setUp(self):
        self.gateway = LocalGateway(app, Config())

    def test_post_next(self):
        body = {"available": ["PAGE_1", "PAGE_2", "PAGE_3", "PAGE_4", "PAGE_5"], 
                "visited": ["PAGE_1", "PAGE_3", "PAGE_5"],
                "state": "PAGE_3",
                "reward": 700}
        response = self.gateway.handle_request(method='POST',
                                               path='/next',
                                               headers={
                                                  'Content-Type': 'application/json'
                                               },
                                               body=json.dumps(body))

        logging.info(response)

        body = json.loads(response['body'])

        assert response['statusCode'] == 200
        assert body.get('state') in ["PAGE_2", "PAGE_4"]

    def test_all_visited(self):
        body = {"available": ["PAGE_1", "PAGE_2", "PAGE_3", "PAGE_4", "PAGE_5"], 
                "visited": ["PAGE_1", "PAGE_2", "PAGE_3", "PAGE_4", "PAGE_5"],
                "state": "PAGE_3",
                "reward": 700}
        response = self.gateway.handle_request(method='POST',
                                               path='/next',
                                               headers={
                                                  'Content-Type': 'application/json'
                                               },
                                               body=json.dumps(body))

        logging.info(response)

        body = json.loads(response['body'])

        assert response['statusCode'] == 200
        assert body.get('state') is None


if __name__ == '__main__':
    unittest.main()