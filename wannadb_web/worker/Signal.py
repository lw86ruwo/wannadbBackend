from typing import Any


class Signals:

	def __init__(self):
		self.status = Signal("status")
		self.finished = Signal("finished")
		self.error = Signal("error")
		self.document_base_to_ui = Signal("document_base_to_ui")
		self.statistics_to_ui = Signal("statistics_to_ui")
		self.feedback_request_to_ui = Signal("feedback_request_to_ui")
		self.cache_db_to_ui = Signal("cache_db_to_ui")


class Signal:
	msg: [Any]

	def __init__(self, signal_type: str):
		self.type = signal_type

	def emit(self, *args: Any):
		self.msg = []
		for arg in args:
			self.msg.append(arg)
