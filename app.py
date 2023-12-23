import logging

from flask import Flask, make_response, current_app, render_template, render_template_string
from flask_cors import CORS
from flask_debugtoolbar import DebugToolbarExtension

from flask_app.core import core_routes
from flask_app.dev import dev_routes
from flask_app.files import main_routes
from flask_app.user import user_management
from wannadb_web_api.Web_Thread_Manager import Web_Thread_Manager

PROFILE = False

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)
app.config["DEBUG"] = True

app.config['SECRET_KEY'] = 'secret!'
toolbar = DebugToolbarExtension(app)


if PROFILE:
	from flask_profiler import flask_profiler
	app.config["flask_profiler"] = {
		"enabled": app.config["DEBUG"],
		"storage": {
			"engine": "sqlite"
		},
		"basicAuth": {
			"enabled": True,
			"username": "",
			"password": ""
		},
		"ignore": [
			"^/static/.*"
		]
	}


# Create the Web_Thread_Manager
web_Thread_Manager = Web_Thread_Manager()
web_Thread_Manager.start()

with app.app_context():
	current_app.web_Thread_Manager = web_Thread_Manager

if PROFILE:
	flask_profiler.init_app(app)

# Register the blueprints
app.register_blueprint(main_routes)
app.register_blueprint(user_management)
app.register_blueprint(dev_routes)
app.register_blueprint(core_routes)


@app.errorhandler(404)
def not_found_error(error):
	return make_response({'error': f'Not Found  \n {error}'}, 404)


@app.errorhandler(Exception)
def generic_error(error):
	return make_response({'error': f'Internal Server Error \n {error}'}, 500)


@app.route('/')
def hello_world():
	return 'Hello'

@app.route('/form')
def index():
	html_code = """
	<html lang="ts">
		<body>
			<form action="/login" method="POST">
				<p>name <input type="text" name="name" /></p>
				<p>age <input type="number" name="age" /></p>
				<p><input type="submit" value="Submit" /></p>
			</form>
		</body>
	</html>
	"""
	return render_template_string(html_code)

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8000, debug=True)
