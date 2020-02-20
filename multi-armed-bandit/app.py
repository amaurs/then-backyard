import logging
import random
import os

import boto3
import urllib.parse
from chalice import Chalice, Response

app = Chalice(app_name='multi-armed-bandit')
app.log.setLevel(logging.INFO)

@app.route('/order', methods=['POST'], cors=True)
def order():
    request = app.current_request
    body = request.json_body
    
    states = body.get("states")
    app.log.info("States available: %s" % states)
    new_order = random.sample(states, len(states))
    app.log.info("New order: %s" % new_order)

    return Response(body={'order': new_order},
                    status_code=200)


def write_metric(state, value):

    cloudwatch = boto3.client('cloudwatch')
    response = cloudwatch.put_metric_data(
        MetricData=[
            {
                'MetricName': state,
                'Dimensions': [
                    {
                        'Name': 'Stage',
                        'Value': 'dev'
                    },
                    {
                        'Name': 'RetentionLowerBound',
                        'Value': value
                    },
                ],
                'Unit': 'Count',
                'Value': 1
            },
        ],
        Namespace='MultiArmedBandit'
    )

    app.log.info(response)

@app.route('/metric', methods=['POST'], cors=True)
def metric():
    request = app.current_request
    body = request.json_body

    app.log.info("State reward: %s" % body.get("state"))
    app.log.info("Total time: %s" % body.get("reward"))

    write_metric(body.get("state"), body.get("reward"))

    return Response(body={},
                    status_code=200)


@app.route('/wigglegrams', methods=['GET'], cors=True)
def list():
    s3 = boto3.resource('s3')
    bucket = 'wigglegrams'
    bucket_list = s3.Bucket(bucket)

    url_base = os.getenv("WIGGLEGRAM_URL", "https://%s.s3.amazonaws.com" % bucket)

    images = [{"url": urllib.parse.urljoin(url_base, file.key)} for file in bucket_list.objects.all()]
    app.log.info("Files found: %s" % images)

    return Response(body={'images': images},
                    status_code=200)