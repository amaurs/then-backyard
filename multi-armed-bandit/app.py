import json
import logging
import random
import os

import boto3
import urllib.parse
from chalice import Chalice, Response
import markovify

app = Chalice(app_name='multi-armed-bandit')
app.log.setLevel(logging.INFO)

EPSILON = 0.15

es_file = os.path.join(os.path.dirname(__file__), 'chalicelib', 'boleros_es.txt')
en_file = os.path.join(os.path.dirname(__file__), 'chalicelib', 'boleros_en.txt')


with open(es_file) as f:
    text = f.read()
    text_model_es = markovify.Text(text)

with open(en_file) as f:
    text = f.read()
    text_model_en = markovify.Text(text)



class RankStatistics:

    _instance = None

    def __init__(self):
        self.statistics = self._load()

    def _load(self):
        s3 = boto3.resource('s3')

        content_object = s3.Object("multiarmed-bandit-statistics", "last-month.json")
        file_content = content_object.get()['Body'].read().decode('utf-8')
        return json.loads(file_content)
    @classmethod
    def instance(cls):
        if cls._instance == None:
            cls._instance = RankStatistics()
        return cls._instance

    def score(self, name):
        print(self.statistics)
        print(name)
        return self.statistics.get(name)

@app.route('/order', methods=['POST'], cors=True)
def order():
    request = app.current_request
    body = request.json_body
    
    states = body.get("states")
    app.log.info("States available: %s" % states)

    states_with_score = []

    for state in states:
        score = RankStatistics.instance().score(state[0])
        if score is not None:
            states_with_score.append((state, score))
        else:
            states_with_score.append((state, 0))

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


@app.route('/wigglegrams/{key}', methods=['GET'], cors=True)
def list(key):
    s3 = boto3.resource('s3')
    bucket = 'wigglegrams'
    bucket_list = s3.Bucket(bucket)

    url_base = os.getenv("WIGGLEGRAM_URL", "https://%s.s3.amazonaws.com" % bucket)

    images = [{"url": urllib.parse.urljoin(url_base, file.key)} for file in bucket_list.objects.filter(Prefix=key) if not file.key.endswith("/")]
    app.log.info("Files found: %s" % images)

    return Response(body={'images': images},
                    status_code=200)

@app.route('/boleros/es', cors=True)
def sentence_es():
    d = {'sentence':text_model_es.make_short_sentence(100).lower()}
    return json.dumps(d, ensure_ascii=False)

@app.route('/boleros/en', cors=True)
def sentence_en():
    d = {'sentence':text_model_en.make_short_sentence(100).lower()}
    return json.dumps(d, ensure_ascii=False)


