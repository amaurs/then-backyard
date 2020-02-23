import json
import logging
import unittest
from unittest import mock

from chalice.config import Config
from chalice.local import LocalGateway

from app import app, RankStatistics


class TestApp(unittest.TestCase):
    def setUp(self):
        self.gateway = LocalGateway(app, Config())

    @mock.patch("app.RankStatistics._load")
    def test_contains_all(self, mock_statistics_load):
        mock_statistics_load.return_value = {
            "PAGE_1": 5,
            "PAGE_2": 4,
            "PAGE_3": 7,
            "PAGE_4": 2
        }
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

    @mock.patch("app.write_metric", return_value=None)
    def test_reward(self, mock_write_metric):
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
        mock_write_metric.assert_called_once()
