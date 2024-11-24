import hashlib
import json
import random
import os
import uuid
import csv
import math
import jwt
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from functools import cache
from typing import List, Dict

import boto3
import subprocess

from botocore.exceptions import ClientError
from chalice import Chalice, Response
from chalice.app import ConvertToMiddleware, AuthRequest, AuthResponse, UnauthorizedError
from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer
import markovify

from chalicelib.modules.container import container

app = Chalice(app_name='then-backyard')
logger = Logger()
tracer = Tracer()

app.register_middleware(ConvertToMiddleware(logger.inject_lambda_context))
app.register_middleware(ConvertToMiddleware(tracer.capture_lambda_handler))


@app.authorizer()
def jwt_auth(auth_request: AuthRequest) -> AuthResponse:
    token = auth_request.token
    logger.info(f"Evaluating authorization token={token}")
    try:
        client = boto3.client(service_name='secretsmanager', region_name='us-east-1')
        jwt.decode(
            jwt=token,
            key=client.get_secret_value(SecretId=os.getenv("JWT_SECRET_NAME")).get('SecretString'),
            algorithms=["HS256"])
        return AuthResponse(routes=['*'], principal_id='faunita')
    except jwt.InvalidTokenError:
        return AuthResponse(routes=[], principal_id='faunita')


@app.middleware('http')
def inject_route_info(event, get_response):
    logger.structure_logs(append=True, request_path=event.path)
    return get_response(event)


EPSILON = 0.15

FROM = 0
TO = 1
FACTOR = 1000
ONE_DAY_IN_SECONDS = 86400

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
    logger.info("States available: %s" % states)

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

    logger.info("New order: %s" % new_order)

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

    logger.info(response)

@app.route('/metric', methods=['POST'], cors=True)
def metric():
    request = app.current_request
    body = request.json_body

    logger.info("State reward: %s" % body.get("state"))
    logger.info("Total time: %s" % body.get("reward"))

    write_metric(body.get("state"), body.get("reward"))

    return Response(body={},
                    status_code=200)

def list_bucket(bucket: str, prefix: str) -> List[str]:
    s3 = boto3.resource('s3')
    bucket_list = s3.Bucket(bucket)

    files = [file.key.split("/")[-1] for file in bucket_list.objects.filter(Prefix=prefix) if
        not file.key.endswith("/")]

    return files
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
    logger.info("Files found: %s" % images)

    return images

@cache
@app.route('/photography', methods=['GET'], cors=True)
def photography():
    return Response(body={'images': list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix="photography")},
                    status_code=200)

@cache
@app.route('/colors/{project}/{resolution}', methods=['GET'], cors=True)
def colors(project: str, resolution: str) -> Response:
    return Response(
        body={'images': list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"colors/{project}/{resolution}")},
        status_code=200)


def read_color_config(slug: str) -> Dict:
    try:
        s3 = boto3.resource('s3')
        content_object = s3.Object(os.getenv("S3_BUCKET_NAME"), f'colors/{slug}/config.json')
        return json.loads(content_object.get()['Body'].read().decode('utf-8'))
    except ClientError:
        return {
            "default": None,
            "description": None
        }


@cache
@app.route('/colors', methods=['GET'], cors=True)
def colors() -> Response:
    s3_client = boto3.client('s3')
    s3 = boto3.resource('s3')
    bucket_list = s3.Bucket(os.getenv("S3_BUCKET_NAME"))

    projects = defaultdict(dict)
    CUBE = "cube"
    SQUARE = "square"

    for obj in bucket_list.objects.filter(Prefix='colors/'):
        if len(url_structure := obj.key.split("/")) == 4:
            prefix, slug, resolution, file = url_structure
            if SQUARE in file:
                signed_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': os.getenv("S3_BUCKET_NAME"),
                            'Key': obj.key},
                    ExpiresIn=ONE_DAY_IN_SECONDS)
                if resolution not in projects[slug]:
                    projects[slug].update({resolution: {SQUARE: signed_url}})
                else:
                    projects[slug][resolution].update({SQUARE: signed_url})
            if CUBE in file:
                signed_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': os.getenv("S3_BUCKET_NAME"),
                            'Key': obj.key},
                    ExpiresIn=ONE_DAY_IN_SECONDS)
                if resolution not in projects[slug]:
                    projects[slug].update({resolution: {CUBE: signed_url}})
                else:
                    projects[slug][resolution].update({CUBE: signed_url})

    return Response(
        body={"colors": [
            {
                "slug": key,
                **read_color_config(key),
                "resolutions": [
                    {
                        "resolution": resolution,
                        "cube": images["cube"],
                        "square": images["square"],
                    } for resolution, images in value.items()]
            } for key, value in projects.items()]
        },
        status_code=200)

@cache
@app.route('/color/{slug}/{resolution}', methods=['GET'], cors=True)
def color(slug: str, resolution: str) -> Response:
    images = list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"colors/{slug}/{resolution}")

    reponse = {
        "cube": None,
        "square": None,
        "slug": slug,
        "resolution": resolution,
    }

    for image in images:
        if "cube" in image["url"]:
            reponse.update({"cube": image["url"]})
        if "square" in image["url"]:
            reponse.update({"square": image["url"]})

    return Response(
        body=reponse,
        status_code=200)

@cache
@app.route('/posts', methods=['GET'], cors=True)
def posts() -> Response:
    return Response(
        body={'posts': list_bucket(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"blog")},
        status_code=200)

@cache
@app.route('/post/{filename}', methods=['GET'], cors=True)
def post(filename: str) -> Response:
    s3_client = boto3.client('s3')

    s3 = boto3.resource('s3')
    markdown = s3.Object(os.getenv("S3_BUCKET_NAME"), f"blog/{filename}").get()['Body'].read().decode('utf-8')

    return Response(
        body={'url': s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': os.getenv("S3_BUCKET_NAME"),
                    'Key': f"blog/{filename}"},
            ExpiresIn=60),
            'markdown': markdown,
            'slug': filename},
        status_code=200)

@cache
@app.route('/codes', methods=['GET'], cors=True)
def codes() -> Response:
    s3 = boto3.resource('s3')

    content_object = s3.Object(os.getenv("S3_BUCKET_NAME"), 'qr/mappings.json')
    file_content = content_object.get()['Body'].read().decode('utf-8')
    mappings = json.loads(file_content)

    links = []
    for key, value in mappings.items():
        links.append({'code': key, 'redirect': value})

    return Response(
        body={'codes': links},
        status_code=200)

@app.route('/boleros/es', cors=True)
def sentence_es():
    d = {'sentence': text_model_es.make_short_sentence(100).lower()}
    return json.dumps(d, ensure_ascii=False)

@app.route('/boleros/en', cors=True)
def sentence_en():
    d = {'sentence': text_model_en.make_short_sentence(100).lower()}
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
    logger.info(" ".join(cmd))
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
        logger.info(line)

def implement_tour(tour_file, cities):
    final_tour = []
    with open(tour_file, 'r') as file_handle:
        csv_reader = csv.reader(file_handle, delimiter=' ')
        next(csv_reader)  # skip the first row which do not contain any city
        first = None
        for edge in csv_reader:
            logger.info("edge %s" % edge)
            if first is None:
                first = cities[int(edge[FROM])]
            final_tour += cities[int(edge[FROM])]
        final_tour += first
    return final_tour

@app.route('/', methods=['POST'], cors=True)
def index():
    body = app.current_request.json_body
    logger.info("headers: %s", app.current_request.headers)
    logger.info("context: %s", app.current_request.context)
    logger.info("json_body: %s", app.current_request.json_body)
    logger.info("method: %s", app.current_request.method)
    logger.info("query_params: %s", app.current_request.query_params)
    logger.info("raw_body: %s", app.current_request.raw_body)
    logger.info("stage_vars: %s", app.current_request.stage_vars)
    logger.info("to_dict: %s", app.current_request.to_dict)
    logger.info("uri_params: %s", app.current_request.uri_params)
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
    logger.info(dim)
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

@app.route('/names', methods=['GET'], cors=True)
def get_names():
    try:
        s3 = boto3.resource('s3')
        content_object = s3.Object(os.getenv("S3_BUCKET_NAME"), 'names.json')
        return {"names": json.loads(content_object.get()['Body'].read().decode('utf-8'))}
    except ClientError:
        return {
            "default": None,
            "description": None
        }

@app.route('/names', methods=['PUT'], cors=True)
def update_names():
    try:
        names = json.loads(app.current_request.query_params.get('names'))
        s3 = boto3.resource('s3')
        content_object = s3.Object(os.getenv("S3_BUCKET_NAME"), 'names.json')
        content_object.put(Body=(bytes(json.dumps(names).encode('UTF-8'))))
        return {"names": names}
    except ClientError:
        return {
            "default": None,
            "description": None
        }


@cache
@app.route('/calendar/{user}', methods=['GET'], authorizer=jwt_auth, cors=True)
def calendar(user: str) -> Response:
    logger.info(
        "Route authorized for user.",
        extra={"data": {"context": app.current_request.context}})
    return Response(
        body={
            'start': {
                'year': 1986,
                'month': 3,
                'day': 23
            },
            'photos': container.photo_service().get_photo_counts_by_date(
                prefix=f"calendar/{user}",
                bucket=os.getenv("S3_BUCKET_NAME"))
        },
        status_code=200)


@cache
@app.route('/calendars/{user}/{key}', methods=['GET'], authorizer=jwt_auth, cors=True)
def calendars(user: str, key: str) -> Response:
    logger.info(
        "Route authorized for user.",
        extra={"data": {"context": app.current_request.context}})
    photos = list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"calendar/{user}/{key.replace('-', '/')}")
    return Response(
        body={'photos': [photo.get("url") for photo in photos]},
        status_code=200)

@cache
@app.route('/no-cors-calendar/{user}', authorizer=jwt_auth)
def no_cors_calendar(user: str) -> Response:
    logger.info(
        "Route authorized for user.",
        extra={"data": {"context": app.current_request.context}})
    return Response(
        body={
            'start': {
                'year': 1986,
                'month': 3,
                'day': 23
            },
            'photos': container.photo_service().get_photo_counts_by_date(
                prefix=f"calendar/{user}",
                bucket=os.getenv("S3_BUCKET_NAME"))
        },
        status_code=200)

@cache
@app.route('/no-cors-calendars/{user}/{key}', authorizer=jwt_auth)
def no_cors_calendars(user: str, key: str) -> Response:
    logger.info(
        "Route authorized for user.",
        extra={"data": {"context": app.current_request.context}})
    photos = list_helper(bucket=os.getenv("S3_BUCKET_NAME"), prefix=f"calendar/{user}/{key.replace('-', '/')}")
    return Response(
        body={'photos': [photo.get("url") for photo in photos]},
        status_code=200)


@app.route('/flyer', methods=['GET'], cors=True)
def flyer() -> Response:
    s3 = boto3.resource('s3')
    content_object = s3.Object(os.getenv("S3_BUCKET_NAME"), f'flyer.json')
    data = json.loads(content_object.get()['Body'].read().decode('utf-8'))
    country = None
    if 'cloudfront-viewer-country' in app.current_request.headers:
        country = app.current_request.headers['cloudfront-viewer-country']
        logger.info(f"Country from headers is: {country}")
    if country and country == "MX":
        info = data[country]
    else:
        info = data["US"]
    return Response(
        body=info,
        status_code=200)

@app.route('/login', methods=['POST'], cors=True)
def login():
    client = boto3.client(service_name='secretsmanager', region_name='us-east-1')
    request = app.current_request
    body = request.json_body
    password = body.get("password")
    hashed_password = hashlib.md5(password.encode()).hexdigest()
    logger.info(f"Hashed requested password: {hashed_password}")
    if hashed_password != client.get_secret_value(
            SecretId=os.getenv("HASHED_PASSWORD_SECRET_NAME")).get('SecretString'):
        logger.info(f"Incorrect password.")
        raise UnauthorizedError("Incorrect password.")
    secret = client.get_secret_value(SecretId=os.getenv("JWT_SECRET_NAME")).get('SecretString')
    token = jwt.encode({"exp": datetime.now(tz=timezone.utc) + timedelta(hours=1)}, secret, algorithm="HS256")
    return Response(
        body={'token': token},
        status_code=200)


