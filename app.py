import logging
import os

from celery import Celery, Task
from flask import Flask, make_response, render_template_string
from flask_cors import CORS
from flask_debugtoolbar import DebugToolbarExtension

from wannadb_web.routing.core import core_routes
from wannadb_web.routing.dev import dev_routes
from wannadb_web.routing.user import user_management
from wannadb_web.routing.files import main_routes

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)
app.config["DEBUG"] = True

app.config['SECRET_KEY'] = 'secret!'
toolbar = DebugToolbarExtension(app)
app.config['DEBUG_TB_PROFILER_ENABLED'] = True


def celery_init_app(_app: Flask) -> Celery:
	class FlaskTask(Task):
		def __call__(self, *args: object, **kwargs: object) -> object:
			with _app.app_context():
				return self.run(*args, **kwargs)

	celery_app = Celery(_app.name, task_cls=FlaskTask)
	celery_app.config_from_object(_app.config["CELERY"])
	celery_app.set_default()
	_app.extensions["celery"] = celery_app
	return celery_app


app = Flask(__name__)
app.config.from_mapping(
	CELERY=dict(
		broker_url=os.environ.get("CELERY_BROKER_URL"),
		task_ignore_result=True,

	),
)
celery = celery_init_app(app)

# Register the blueprints
app.register_blueprint(main_routes)
app.register_blueprint(user_management)
app.register_blueprint(dev_routes)
app.register_blueprint(core_routes)

app.app_context()


@app.errorhandler(404)
def not_found_error(error):
	return make_response({'error': f'Not Found  \n {error}'}, 404)


@app.errorhandler(Exception)
def generic_error(error):
	return make_response({'error': f'Internal Server Error \n {error}'}, 500)


@app.route('/')
@app.route('/DEBUG')
def index():
	html_code = """
	<html lang="ts">
		<body>
			<form>
				<p>hello</p>
			</form>
		</body>
	</html>
	"""
	return render_template_string(html_code)


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8000, debug=True)
