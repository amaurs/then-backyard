import logging
import random

from chalice import Chalice, Response

app = Chalice(app_name='multi-armed-bandit')


@app.route('/next', methods=['POST'])
def index():
    request = app.current_request
    body = json.loads(app.current_request.raw_body.decode())

    app.log.info(body)
    app.log.info(body.get("available"))
    app.log.info(body.get("visited"))
    app.log.info(body.get("state"))
    app.log.info(body.get("reward"))



    new_state = random.choice(list(set(body.get("available")) - set(body.get("visited"))))


    return Response(body={'state': new_state},
                    status_code=200)
