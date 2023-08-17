from collections import Counter
from dataclasses import dataclass
from aws_lambda_powertools import Logger
from typing import List, Union

from botocore.client import BaseClient

logger = Logger()


@dataclass
class Photo:
    s3_resource: BaseClient

    def get_photo_counts_by_date(self, prefix: str, bucket: str) -> List[List[Union[str, int]]]:
        bucket_list = self.s3_resource.Bucket(bucket)
        files = [file.key[len(prefix) + 1: len(prefix) + 11] for file in bucket_list.objects.filter(Prefix=prefix) if
                 not file.key.endswith("/")]

        logger.info(f"Processing {bucket} bucket to count photos.")

        return [[key, count] for key, count in Counter(files).items()]
