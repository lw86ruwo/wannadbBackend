import random
import time

from celery import current_app

from wannadb.data.data import Document, Attribute
from wannadb.interaction import InteractionCallback
from wannadb.statistics import Statistics
from wannadb.status import StatusCallback
from wannadb_web.postgres.queries import getDocument
from wannadb_web.worker.Signal import Signals
from wannadb_web.worker.Web_API import WannaDB_WebAPI
from wannadb_web.worker.util import TaskStatus, Progress, State


@current_app.task(bind=True)
def create_document_base(self, document_names: [str], attribute: [Attribute], statistics: [Statistics]):
	signals = Signals()

	try:
		for document_name in document_names:
			getDocument(document_name)


	document = Document(document_name)
	def status_callback_fn(message, progress):
		self.update_state(state=message, meta=progress)

	def interaction_callback_fn(pipeline_element_identifier, feedback_request):
		feedback_request["identifier"] = pipeline_element_identifier
		self.feedback_request_to_ui.emit(feedback_request)

		self.feedback_mutex.lock()
		try:
			self.feedback_cond.wait(self.feedback_mutex)
		finally:
			self.feedback_mutex.unlock()

		return self.feedback

	status_callback = StatusCallback(status_callback_fn)
	interaction_callback = InteractionCallback(interaction_callback_fn)

	try:
		wannaDB_WebAPI = WannaDB_WebAPI(1, signals, status_callback, interaction_callback)
		wannaDB_WebAPI.create_document_base(document, attribute, statistics)

	except Exception as e:
		self.update_state(state=State.FAILURE.value, meta={'exception': str(e)})
		raise


@current_app.task(bind=True)
def long_task(self):
	try:
		"""Background task that runs a long function with progress reports."""
		verb = ['Starting up', 'Booting', 'Repairing', 'Loading', 'Checking']
		adjective = ['master', 'radiant', 'silent', 'harmonic', 'fast']
		noun = ['solar array', 'particle reshaper', 'cosmic ray', 'orbiter', 'bit']
		data = ''
		total = random.randint(10, 50)
		status = TaskStatus(Progress(0, total), data)
		self.update_state(state=status.state, meta=status.meta)
		for i in range(total):
			if not data or random.random() < 0.25:
				data = '{0} {1} {2}...'.format(random.choice(verb),
											   random.choice(adjective),
											   random.choice(noun))
			time.sleep(1)
			status.update(i + 1, data)
			print(status)
			self.update_state(state=status.state, meta=status.meta)
		self.update_state(state=status.state, meta=status.meta)
		return data
	except Exception as e:
		self.update_state(state=State.FAILURE.value, meta={'exception': str(e)})
		raise
