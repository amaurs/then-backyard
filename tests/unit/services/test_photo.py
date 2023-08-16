import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from boto3.resources.base import ServiceResource
from chalicelib.services.photo import Photo


class TestPhoto(unittest.TestCase):

    def test_get_photo_counts_by_date(self):
        # given
        mock_bucket = MagicMock()
        mock_s3_resource = MagicMock(spec=ServiceResource, Bucket=mock_bucket)
        photo_service = Photo(s3_resource=mock_s3_resource)
        prefix = "magic/bananas"
        expected_bucket = "shenanigans"
        mock_s3_resource.Bucket.return_value.objects.filter.return_value = [
            SimpleNamespace(key="magic/bananas/2023/01/23/4"),
            SimpleNamespace(key="magic/bananas/2023/01/23/2"),
            SimpleNamespace(key="magic/bananas/2023/01/23/0"),
            SimpleNamespace(key="magic/bananas/2023/02/23/8"),
            SimpleNamespace(key="magic/bananas/2023/02/23/0"),
            SimpleNamespace(key="magic/bananas/2023/03/23/7"),
        ]
        expected = [['2023/01/23', 3], ['2023/02/23', 2], ['2023/03/23', 1]]

        # when
        actual = photo_service.get_photo_counts_by_date(prefix=prefix, bucket=expected_bucket)

        # then
        mock_s3_resource.Bucket.assert_called_once_with(expected_bucket)
        mock_s3_resource.Bucket.return_value.objects.filter.assert_called_once_with(Prefix='magic/bananas')
        self.assertEqual(expected, actual)
