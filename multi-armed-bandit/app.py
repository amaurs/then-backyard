import logging
import random

from chalice import Chalice, Response

app = Chalice(app_name='multi-armed-bandit')


@app.route('/next', methods=['POST'], cors=True)
def index():
    request = app.current_request
    body = request.json_body


    logging.info(body.get("available"))
    logging.info(body.get("visited"))
    logging.info(body.get("state"))
    logging.info(body.get("reward"))



    new_state = random.choice(list(set(body.get("available")) - set(body.get("visited"))))


    return Response(body={'state': new_state},
                    status_code=200)
