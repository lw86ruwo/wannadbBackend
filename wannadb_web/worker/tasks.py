import random
import time

from celery import current_app
from wannadb_web.worker.util import TaskStatus, Progress, State


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
			status.update(i+1, data)
			print(status)
			self.update_state(state=status.state, meta=status.meta)
		self.update_state(state=status.state, meta=status.meta)
		return data
	except Exception as e:
		self.update_state(state=State.FAILURE.value, meta={'exception': str(e)})
		raise
