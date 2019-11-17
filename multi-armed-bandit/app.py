import logging
import random

from chalice import Chalice, Response

app = Chalice(app_name='multi-armed-bandit')


@app.route('/next', methods=['POST'], cors=True)
def index():
    request = app.current_request
    body = request.json_body

    app.log.info(body)
    app.log.info(body.get("available"))
    app.log.info(body.get("visited"))
    app.log.info(body.get("state"))
    app.log.info(body.get("reward"))


    eligible = list(set(body.get("available")) - set(body.get("visited")))

    new_state = None
    if eligible:
        new_state = random.choice(eligible)

    return Response(body={'state': new_state},
                    status_code=200)
