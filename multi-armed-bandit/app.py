import json
import logging
import random
import os

import boto3
import urllib.parse
from chalice import Chalice, Response

app = Chalice(app_name='multi-armed-bandit')
app.log.setLevel(logging.INFO)

EPSILON = 0.15

class RankStatistics:

    _instance = None

    def __init__(self):
        self.statistics = self._load()

    def _load(self):
        s3 = boto3.resource('s3')

        content_object = s3.Object(os.getenv("STATISTICS_BUCKET"), os.getenv("STATISTICS_KEY"))
        file_content = content_object.get()['Body'].read().decode('utf-8')
        return json.loads(file_content)
    @classmethod
    def instance(cls):
        if cls._instance == None:
            cls._instance = RankStatistics()
        return cls._instance

    def score(self, name):

        return self.statistics.get(name)

@app.route('/order', methods=['POST'], cors=True)
def order():
    request = app.current_request
    body = request.json_body
    
    states = body.get("states")
    app.log.info("States available: %s" % states)

    states_with_score = [(state, RankStatistics.instance().score(state)) for state in states if
                         RankStatistics.instance().score(state)]

    states_sorted = sorted(states_with_score, key=lambda state: state[1])

    new_order = []

    for count in range(len(states_sorted)):
        if random.random() < EPSILON:
            # explore
            current_choice = random.choice(states_sorted)
            states_sorted.remove(current_choice)
        else:
            # exploit
            current_choice = states_sorted.pop()
        new_order.append(current_choice[0])

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
                        'Value': str(value)
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


if __name__ == '__main__':

    import random

    print(RankStatistics.instance().score("/conway"))

    names = [key for key in RankStatistics.instance().statistics.keys()] + ["/new"]

    print(names)

    states_with_score = [(key, RankStatistics.instance().score(key)) for key in names if RankStatistics.instance().score(key)]


    random.shuffle(states_with_score)

    print(states_with_score)

    states_sorted = sorted(states_with_score, key=lambda state: state[1])

    final = []

    for i in range(len(states_sorted)):

        if random.random() < EPSILON:
            # explore
            print("explore")
            choice = random.choice(states_sorted)

            states_sorted.remove(choice)


        else:
            # exploit
            print("exploit")
            choice = states_sorted.pop()

        final.append(choice[0])

        app.log.info(states_sorted)
        app.log.info(final)







