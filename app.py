import json
import logging
import random
import os
import uuid
import csv
import math
from typing import List

import boto3
import subprocess
from chalice import Chalice, Response
import markovify

app = Chalice(app_name='then-backyard')
app.log.setLevel(logging.INFO)

EPSILON = 0.15

FROM = 0
TO = 1
FACTOR = 1000

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


def list_helper(bucket: str, prefix: str) -> List[str]:
    s3 = boto3.resource('s3')
    bucket_list = s3.Bucket(bucket)
    s3_client = boto3.client('s3')

    images = [{"url": s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket,
                'Key': file.key},
        ExpiresIn=60)} for file in bucket_list.objects.filter(Prefix=prefix) if
        not file.key.endswith("/")]
    app.log.info("Files found: %s" % images)

    return images

@app.route('/photography', methods=['GET'], cors=True)
def photography():
    return Response(body={'images': list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix="photography")},
                    status_code=200)


@app.route('/colors/{project}/{resolution}', methods=['GET'], cors=True)
def colors(project: str, resolution: str) -> Response:
    return Response(
        body={'images': list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"colors/{project}/{resolution}")},
        status_code=200)

@app.route('/posts', methods=['GET'], cors=True)
def posts() -> Response:
    return Response(
        body={'posts': list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"blog")},
        status_code=200)
@app.route('/boleros/es', cors=True)
def sentence_es():
    d = {'sentence':text_model_es.make_short_sentence(100).lower()}
    return json.dumps(d, ensure_ascii=False)

@app.route('/boleros/en', cors=True)
def sentence_en():
    d = {'sentence':text_model_en.make_short_sentence(100).lower()}
    return json.dumps(d, ensure_ascii=False)



def create_instance_3d(filename, n_cities, point_set):
    cities = []
    with open(filename, "w+") as file_handle:
        file_handle.write("%d\n" % n_cities)
        for i in range(n_cities):
            if point_set == "moebius":
                city = generate_random_moebius()
            elif point_set == "sphere":
                city = generate_random_sphere()
            elif point_set == "torus":
                city = generate_random_torus()
            elif point_set == "tree_foil":
                city = generate_random_trefoil()
            elif point_set == "helix":
                city = generate_random_helix()
            elif point_set == "plane":
                city = generate_random_plane()
            file_handle.write("%s %s %s\n" % (city[0] * FACTOR, city[1] * FACTOR, city[2] * FACTOR))
            cities.append(city)
        file_handle.write("EOF\n")
    return cities




def create_instance_from_cities_3d(filename, cities):
    final_cities = []
    with open(filename, "w+") as file_handle:
        print(len(cities) / 3)
        file_handle.write("%d\n" % (len(cities) / 3))
        for i in range(0, len(cities), 3):
            city = [cities[i], cities[i + 1], cities[i + 2]]
            print(city)
            file_handle.write("%s %s %s\n" % (city[0], city[1], city[2]))
            final_cities.append(city)
        file_handle.write("EOF\n")
    return final_cities

def create_instance_from_cities_2d(filename, cities):
    final_cities = []
    with open(filename, "w+") as file_handle:
        print(len(cities) / 2)
        file_handle.write("%d\n" % (len(cities) / 2))
        for i in range(0, len(cities), 2):
            city = [cities[i], cities[i + 1]]
            print(city)
            file_handle.write("%s %s\n" % (city[0], city[1]))
            final_cities.append(city)
        file_handle.write("EOF\n")
    return final_cities


def generate_random_moebius():
    s = random.random() * 2 - 1
    theta = random.random() * math.pi * 2
    return from_moebius_coords(2.0, s, theta)

def from_moebius_coords(radius, s, theta):
    x = (radius + s * math.cos(theta / 2)) * math.cos(theta)
    y = (radius + s * math.cos(theta / 2)) * math.sin(theta)
    z = s * math.sin(theta / 2)
    return [x, y, z]

def generate_random_sphere():
    radius = 1.0
    theta = random.random() * math.pi * 2
    phi = random.random() * math.pi
    return from_sphere_coords(radius, theta, phi)

def from_sphere_coords(rho, theta, phi):
    x = rho * math.cos(theta) * math.sin(phi)
    y = rho * math.sin(theta) * math.sin(phi)
    z = rho * math.cos(phi)
    return [x, y, z]

def generate_random_torus():
    a = 2.0
    c = 1.0
    v = random.random() * math.pi * 2
    u = random.random() * math.pi * 2
    return from_torus_coords(a, c, u, v)

def from_torus_coords(a, c, u, v):
    x = (c * a * math.cos(v)) * math.cos(u)
    y = (c * a * math.cos(v)) * math.sin(u)
    z = a * math.sin(u)
    return [x, y, z]

def generate_random_trefoil():
    u = random.random() * math.pi * 2
    return from_trefoil_coords(u)

def from_trefoil_coords(u):
    x = math.sin(u) + 2.0 * math.sin(2.0 * u)
    y = math.cos(u) - 2.0 * math.cos(2.0 * u)
    z = - math.sin(3.0 * u)
    return [x, y, z]

def generate_random_helix():
    u = random.random() * math.pi * 2
    v = 2.0
    return from_helix_coords(u, v)

def from_helix_coords(u, v):
    x = v * math.cos(u)
    y = v * math.sin(u)
    z = u
    return [x, y, z]

def generate_random_plane():
    x = random.random() * 2 - 1
    y = random.random() * 2 - 1
    z = 0
    return [x, y, z]

def execute(cmd):
    app.log.info(" ".join(cmd))
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)

def call_solver(tsp_file, tour_file, dim=3):
    cmd = ["./chalicelib/linkern", "-o", tour_file, "-N", "%s" % dim, tsp_file]
    for line in execute(cmd):
        app.log.info(line)

def implement_tour(tour_file, cities):
    final_tour = []
    with open(tour_file, 'r') as file_handle:
        csv_reader = csv.reader(file_handle, delimiter=' ')
        next(csv_reader) # skip the first row which do not contain any city
        first = None
        for edge in csv_reader:
            app.log.info("edge %s" % edge)
            if first is None:
                first = cities[int(edge[FROM])]
            final_tour += cities[int(edge[FROM])]
        final_tour += first
    return final_tour

@app.route('/', methods=['POST'], cors=True)
def index():
    body = app.current_request.json_body
    app.log.info("headers: %s", app.current_request.headers)
    app.log.info("context: %s", app.current_request.context)
    app.log.info("json_body: %s", app.current_request.json_body)
    app.log.info("method: %s", app.current_request.method)
    app.log.info("query_params: %s", app.current_request.query_params)
    app.log.info("raw_body: %s", app.current_request.raw_body)
    app.log.info("stage_vars: %s", app.current_request.stage_vars)
    app.log.info("to_dict: %s", app.current_request.to_dict)
    app.log.info("uri_params: %s", app.current_request.uri_params)
    point_set = body['point_set']
    n_cities = min(int(body['n_cities']), 3000)

    tsp_file = "/tmp/%s.tsp" % uuid.uuid4()
    tour_file = "/tmp/%s.tour" % uuid.uuid4()

    cities = create_instance_3d(tsp_file, n_cities, point_set)
    call_solver(tsp_file, tour_file)
    tour = implement_tour(tour_file, cities)


    return tour

@app.route('/solve', methods=['GET'], cors=True)
def solver():
    cities = json.loads(app.current_request.query_params.get('cities'))
    dim = int(app.current_request.query_params.get('dimension', 2))
    app.log.info(dim)
    tsp_file = "/tmp/%s.tsp" % uuid.uuid4()
    tour_file = "/tmp/%s.tour" % uuid.uuid4()

    if dim == 3:

        final_cities = create_instance_from_cities_3d(tsp_file, cities)
        call_solver(tsp_file, tour_file, dim=3)
    elif dim == 2:
        final_cities = create_instance_from_cities_2d(tsp_file, cities)
        call_solver(tsp_file, tour_file, dim=2)

    else:
        return {"status": 500}

    tour = implement_tour(tour_file, final_cities)

    return tour