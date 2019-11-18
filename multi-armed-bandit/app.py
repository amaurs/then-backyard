import logging
import random

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

@app.route('/metric', methods=['POST'], cors=True)
def metric():
    request = app.current_request
    body = request.json_body

    app.log.info("State reward: %s" % body.get("state"))
    app.log.info("Total time: %s" % body.get("reward"))

    return Response(body={},
                    status_code=200)