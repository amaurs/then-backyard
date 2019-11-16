import logging
import random

from chalice import Chalice, Response

app = Chalice(app_name='multi-armed-bandit')


@app.route('/next', methods=['POST'])
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


# The view function above will return {"hello": "world"}
# whenever you make an HTTP GET request to '/'.
#
# Here are a few more examples:
#
# @app.route('/hello/{name}')
# def hello_name(name):
#    # '/hello/james' -> {"hello": "james"}
#    return {'hello': name}
#
# @app.route('/users', methods=['POST'])
# def create_user():
#     # This is the JSON body the user sent in their POST request.
#     user_as_json = app.current_request.json_body
#     # We'll echo the json body back to the user in a 'user' key.
#     return {'user': user_as_json}
#
# See the README documentation for more examples.
#
