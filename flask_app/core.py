"""
core_routes Module

This module defines Flask routes for the 'core' functionality of the Wannadb UI.

It includes a Blueprint named 'core_routes' with routes related to creating document bases.

Routes:
    - /core/create_document_base (POST): Endpoint for creating a document base.


Dependencies:
    - Flask: Web framework for handling HTTP requests and responses.
    - config.tokenDecode: Function for decoding authorization tokens.
    - wannadb_ui.wannadb_api.WannaDBAPI: API for interacting with Wannadb.

Example:
    To create a Flask app and register the 'core_routes' Blueprint:

    ```python
    from flask import Flask
    from core_routes import core_routes

    app = Flask(__name__)
    app.register_blueprint(core_routes)
    ```

Author: Leon Wenderoth
"""
import logging.config

from flask import Blueprint, request, make_response

from config import tokenDecode
from wanadb_web_api.api import WannaDBWebAPI
from wannadb.data.data import Document, Attribute
from wannadb.resources import ResourceManager, MANAGER

core_routes = Blueprint('core_routes', __name__, url_prefix='/core')

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()


@core_routes.route('/create_document_base', methods=['POST'])
def create_document_base():
	# form = request.form
	# authorization = request.headers.get("authorization")
	# _organisation_id = int(form.get("organisationId"))
	#
	# _token = tokenDecode(authorization)
	# _base_name = int(form.get("baseName"))
	document = Document("a", "b")
	attribute = Attribute("a")
	if MANAGER is None:
		with ResourceManager():
			a = WannaDBWebAPI()
			a.create_document_base([document], [attribute], "None")
	else:
		a = WannaDBWebAPI()
		a.create_document_base([document], [attribute], "None")

	return make_response("Document base created", 200)
