import enum
import json
from dataclasses import dataclass, asdict
from typing import Any


class State(enum.Enum):
	STARTED = 'STARTED'
	PENDING = 'PENDING'
	SUCCESS = 'SUCCESS'
	FAILURE = 'FAILURE'

	def __str__(self):
		return self.value


@dataclass(init=True)
class Progress:
	"""Class for representing the progress of a task."""
	current: int
	total: int


@dataclass
class TaskStatus:
	"""Class for representing the response of a task."""

	__state: State
	__progress: Progress
	__data: Any

	def __init__(self, progress: Progress, result: Any, state=State.STARTED):
		self.__state = state
		self.__progress = progress
		self.__data = result

	@property
	def state(self) -> str:
		"""Get the state of the task."""
		return self.__state.value

	@property
	def progress(self) -> Progress:
		"""Get the progress of the task."""
		return self.__progress

	def update(self, current: int, data: Any = None) -> None:
		"""Update the progress of the task."""
		if self.state is State.SUCCESS:
			raise ValueError("The task is already finished.")
		if self.state is State.FAILURE:
			raise ValueError("The task has failed.")
		if self.state is State.STARTED:
			self.__state = State.PENDING
		if current > self.__progress.total:
			raise ValueError("The current progress cannot be greater than the total progress.")
		if current == self.__progress.total:
			self.__state = State.SUCCESS
		self.__progress = Progress(current, self.__progress.total)
		self.__data = data

	@property
	def result(self) -> Any:
		"""Get the data of the task."""
		return self.__data

	@property
	def meta(self):
		"""Convert the TaskState to a JSON string."""
		if self.state is State.SUCCESS:
			return {"data": self.result}
		else:
			return {"progress": asdict(self.progress), "data": json.dumps(self.result)}
