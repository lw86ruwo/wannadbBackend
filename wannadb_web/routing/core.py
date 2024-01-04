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

from flask import Blueprint, make_response, current_app, jsonify, url_for

from wannadb.data.data import Document, Attribute
from wannadb.statistics import Statistics
from wannadb_web.worker.Web_API import create_document_base

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
	document = Document("a", "b")
	attribute = Attribute("a")
	statistics = Statistics(False)

	create_document_base.apply_async(args=([document], [attribute]))

	return make_response("Document base created", 200)


@core_routes.route('/document_base', methods=['GET'])
def getStatus():
	with current_app.app_context():
		print(current_app.web_Thread_Manager.access_thread(1).status.name)
		return current_app.web_Thread_Manager.access_thread(1).status.name


from wannadb_web.worker.tasks import long_task


@core_routes.route('/longtask', methods=['POST'])
def longtask():
	task = long_task.apply_async()
	return jsonify({}), 202, {'Location': url_for('core_routes.taskstatus',
												  task_id=task.id)}


@core_routes.route('/status/<task_id>')
def taskstatus(task_id):
	task = long_task.AsyncResult(task_id)
	if task.state == 'PENDING':
		response = {
			'state': task.state,
			'current': 0,
			'total': 1,
			'status': 'Pending...'
		}
	elif task.state != 'FAILURE':
		response = {
			'state': task.state,
			'current': task.info.get('current', 0),
			'total': task.info.get('total', 1),
			'status': task.info.get('status', '')
		}
		if 'result' in task.info:
			response['result'] = task.info['result']
	else:
		# something went wrong in the background job
		response = {
			'state': task.state,
			'current': 1,
			'total': 1,
			'status': str(task.info),  # this is the exception raised
		}
	return jsonify(response)
