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

from celery.result import AsyncResult
from flask import Blueprint, make_response, current_app, jsonify, url_for

from wannadb.data.data import Document, Attribute
from wannadb.statistics import Statistics
from wannadb_web.worker.tasks import create_document_base, long_task

core_routes = Blueprint('core_routes', __name__, url_prefix='/core')

logger = logging.getLogger(__name__)


@core_routes.route('/document_base', methods=['POST'])
def create_document():
	# form = request.form
	# authorization = request.headers.get("authorization")
	# _organisation_id = int(form.get("organisationId"))
	#
	# _token = tokenDecode(authorization)
	# _base_name = int(form.get("baseName"))
	document_name = "test"
	attribute = Attribute("a")
	statistics = Statistics(False)

	task = create_document_base.apply_async(args=(document_name, [attribute], statistics))

	return make_response("Document base created", 200)


@core_routes.route('/document_base', methods=['GET'])
def getStatus():
	with current_app.app_context():
		print(current_app.web_Thread_Manager.access_thread(1).status.name)
		return current_app.web_Thread_Manager.access_thread(1).status.name


@core_routes.route('/longtask', methods=['POST'])
def longtask():
	task = long_task.apply_async()
	return jsonify(str(task.id)), 202, {'Location': url_for('core_routes.task_status',
															task_id=task.id)}


@core_routes.route('/status/<task_id>')
def task_status(task_id):
	task: AsyncResult = long_task.AsyncResult(task_id)
	meta = task.info or {}
	if task.successful():
		return make_response(meta.get('data'), 200)
	else:
		response = {
			'state': task.state,
			'current': meta.get('progress', {}).get('current', 0),
			'total': meta.get('progress', {}).get('total', 0),
			'data': meta.get('data', ''),
		}
		return jsonify(response)
