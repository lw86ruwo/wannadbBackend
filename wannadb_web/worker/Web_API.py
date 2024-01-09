import csv
import io
import json
import logging
import os
from typing import Optional

from celery import Celery, Task

from wannadb.configuration import Pipeline
from wannadb.data.data import Attribute, Document, DocumentBase
from wannadb.interaction import EmptyInteractionCallback, InteractionCallback
from wannadb.matching.distance import SignalsMeanDistance
from wannadb.matching.matching import RankingBasedMatcher
from wannadb.preprocessing.embedding import BERTContextSentenceEmbedder, RelativePositionEmbedder, \
	SBERTTextEmbedder, SBERTLabelEmbedder
from wannadb.preprocessing.extraction import StanzaNERExtractor, SpacyNERExtractor
from wannadb.preprocessing.label_paraphrasing import OntoNotesLabelParaphraser, \
	SplitAttributeNameLabelParaphraser
from wannadb.preprocessing.normalization import CopyNormalizer
from wannadb.preprocessing.other_processing import ContextSentenceCacher
from wannadb.statistics import Statistics
from wannadb.status import StatusCallback
from wannadb_web.Redis import RedisCache
from wannadb_web.SQLite import Cache_DB
from wannadb_web.SQLite.Cache_DB import SQLiteCacheDBWrapper
from wannadb_web.postgres.queries import getDocument
from wannadb_web.postgres.transactions import addDocument
from wannadb_web.worker.util import TaskStatus, Progress

logger = logging.getLogger(__name__)

# Initialize Celery
celery = Celery('tasks', broker=os.environ.get("CELERY_BROKER_URL"))


@celery.task(bind=True)
def create_document_base(self, _id: int, documents: [Document], attributes: [Attribute], statistics: [Statistics]):
	logger.debug("Called function 'create_document_base'.")
	wrapper_cache_db: Optional[SQLiteCacheDBWrapper] = None
	try:
		wrapper_cache_db = Cache_DB.Cache_Manager.user(_id)
		wrapper_cache_db.reset_cache_db()

		document_base = DocumentBase(documents, attributes)
		wrapper_cache_db.sqLiteCacheDB.create_input_docs_table("input_document", document_base.documents)

		if not document_base.validate_consistency():
			logger.error("Document base is inconsistent!")
			error = "Document base is inconsistent!"
			return error

		# load default preprocessing phase

		# noinspection PyTypeChecker
		preprocessing_phase = Pipeline([
			StanzaNERExtractor(),
			SpacyNERExtractor("SpacyEnCoreWebLg"),
			ContextSentenceCacher(),
			CopyNormalizer(),
			OntoNotesLabelParaphraser(),
			SplitAttributeNameLabelParaphraser(do_lowercase=True, splitters=[" ", "_"]),
			SBERTLabelEmbedder("SBERTBertLargeNliMeanTokensResource"),
			SBERTTextEmbedder("SBERTBertLargeNliMeanTokensResource"),
			BERTContextSentenceEmbedder("BertLargeCasedResource"),
			RelativePositionEmbedder()
		])

		def status_callback_fn(message, progress):
			self.update_state(state='PROGRESS', meta={'progress': progress, 'message': message})

		status_callback = StatusCallback(status_callback_fn)

		preprocessing_phase(document_base, EmptyInteractionCallback(), status_callback, statistics)

		# save_document_base_to_bson(document_base, _id)

		return {'current': 100, 'total': 100, 'status': 'Task completed!'}
	except Exception as e:
		error = str(e)
		return error
	finally:
		if wrapper_cache_db is not None:
			wrapper_cache_db.disconnect()


def load_document_base_from_bson(document_id: int, user_id: int):
	logger.debug("Called function 'load_document_base_from_bson'.")
	wrapper_cache_db: Optional[SQLiteCacheDBWrapper] = None
	try:
		wrapper_cache_db = Cache_DB.Cache_Manager.user(user_id)
		cache_db = wrapper_cache_db.sqLiteCacheDB

		document = getDocument(document_id, user_id)
		if isinstance(document, str):
			logger.error("document is not a DocumentBase!")
			return -1
		document_base = DocumentBase.from_bson(document)

		if not document_base.validate_consistency():
			logger.error("Document base is inconsistent!")
			return -1

		wrapper_cache_db.reset_cache_db()

		for attribute in document_base.attributes:
			cache_db.create_table_by_name(attribute.name)
		cache_db.create_input_docs_table("input_document", document_base.documents)

		logger.info(f"Document base loaded from BSON with ID {document_id}.")
		return document_base

	except Exception as e:
		logger.error(str(e))
		return -1
	finally:
		if wrapper_cache_db is not None:
			wrapper_cache_db.disconnect()


def save_document_base_to_bson(name: str, organisation_id: int, document_base: DocumentBase, user_id: int):
	logger.debug("Called function 'save_document_base_to_bson'.")
	try:
		document_id = addDocument(name, document_base.to_bson(), organisation_id, user_id)
		if document_id is None:
			logger.error("Document base could not be saved to BSON!")
		elif document_id == -1:
			logger.error("Document base could not be saved to BSON! Document name already exists!")
			return -1
		logger.info(f"Document base saved to BSON with ID {document_id}.")
		return document_id
	except Exception as e:
		logger.debug(str(e))


def save_table_to_csv(document_base: DocumentBase):
	logger.debug("Called function 'save_table_to_csv'.")
	try:
		buffer = io.StringIO()

		# check that the table is complete
		for attribute in document_base.attributes:
			for document in document_base.documents:
				if attribute.name not in document.attribute_mappings.keys():
					logger.error("Cannot save a table with unpopulated attributes!")
					return -1

		# TODO: currently stores the text of the first matching nugget (if there is one)
		table_dict = document_base.to_table_dict("text")
		headers = list(table_dict.keys())
		rows = []
		for ix in range(len(table_dict[headers[0]])):
			row = []
			for header in headers:
				if header == "document-name":
					row.append(table_dict[header][ix])
				elif not table_dict[header][ix]:
					row.append(None)
				else:
					row.append(table_dict[header][ix][0])
			rows.append(row)
			writer = csv.writer(buffer, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
			writer.writerow(headers)
			writer.writerows(rows)
	except FileNotFoundError:
		logger.error("Directory does not exist!")
	except Exception as e:
		logger.error(str(e))


def add_attribute(name: str, document_base: DocumentBase):
	logger.debug("Called function 'add_attribute'.")
	try:
		if name in [attribute.name for attribute in document_base.attributes]:
			logger.error("Attribute name already exists!")
			return -1
		elif name == "":
			logger.error("Attribute name must not be empty!")
			return -1
		else:
			document_base.attributes.append(Attribute(name))
			logger.debug(f"Attribute '{name}' added.")
			return 0
	except Exception as e:
		logger.error(str(e))


def add_attributes(names: str, document_base: DocumentBase):
	logger.debug("Called function 'add_attributes'.")
	try:
		already_existing_names = []
		for name in names:
			if name in [attribute.name for attribute in document_base.attributes]:
				logger.info(f"Attribute name '{name}' already exists and was thus not added.")
				already_existing_names.append(name)
			elif name == "":
				logger.info("Attribute name must not be empty and was thus ignored.")
			else:
				document_base.attributes.append(Attribute(name))
				logger.debug(f"Attribute '{name}' added.")
		return already_existing_names
	except Exception as e:
		logger.error(str(e))


def remove_attribute(name: str, document_base: DocumentBase):
	logger.debug("Called function 'remove_attribute'.")
	try:
		if name in [attribute.name for attribute in document_base.attributes]:
			for document in document_base.documents:
				if name in document.attribute_mappings.keys():
					del document.attribute_mappings[name]

			for attribute in document_base.attributes:
				if attribute.name == name:
					document_base.attributes.remove(attribute)
					break
			return 0
		else:
			logger.error("Attribute name does not exist!")
			return -1
	except Exception as e:
		logger.error(str(e))


def forget_matches_for_attribute(name: str, document_base: DocumentBase):
	logger.debug("Called function 'forget_matches_for_attribute'.")
	try:
		if name in [attribute.name for attribute in document_base.attributes]:
			for document in document_base.documents:
				if name in document.attribute_mappings.keys():
					del document.attribute_mappings[name]
			return 0
		else:
			logger.error("Attribute name does not exist!")
			return -1
	except Exception as e:
		logger.error(str(e))


def forget_matches(name: str, user_id: int, document_base: DocumentBase):
	logger.debug("Called function 'forget_matches'.")
	wrapper_cache_db: Optional[SQLiteCacheDBWrapper] = None
	try:
		wrapper_cache_db = Cache_DB.Cache_Manager.user(user_id)
		cache_db = wrapper_cache_db.sqLiteCacheDB

		for attribute in document_base.attributes:
			cache_db.delete_table(attribute.name)
			cache_db.create_table_by_name(attribute.name)
		for document in document_base.documents:
			document.attribute_mappings.clear()
		logger.debug(f"Matche: {name} forgotten.")
		return 0
	except Exception as e:
		logger.error(str(e))
		return -1
	finally:
		if wrapper_cache_db is not None:
			wrapper_cache_db.disconnect()


def save_statistics_to_json(statistics: Statistics):
	logger.debug("Called function 'save_statistics_to_json'.")
	try:
		return json.dumps(statistics.to_serializable(), indent=2)
	except Exception as e:
		logger.error(str(e))


@celery.task(bind=True)
def interactive_table_population(self, document_base: DocumentBase, statistics: Statistics):
	logger.debug("Called function 'interactive_table_population'.")
	status = TaskStatus(Progress(0, 100), None)
	self.update_state(state=status.state, meta=status.meta)
	try:
		matching_phase = Pipeline(
			[
				SplitAttributeNameLabelParaphraser(do_lowercase=True, splitters=[" ", "_"]),
				ContextSentenceCacher(),
				SBERTLabelEmbedder("SBERTBertLargeNliMeanTokensResource"),
				RankingBasedMatcher(
					distance=SignalsMeanDistance(
						signal_identifiers=[
							"LabelEmbeddingSignal",
							"TextEmbeddingSignal",
							"ContextSentenceEmbeddingSignal",
							"RelativePositionSignal"
						]
					),
					max_num_feedback=100,
					len_ranked_list=10,
					max_distance=0.2,
					num_random_docs=1,
					sampling_mode="AT_MAX_DISTANCE_THRESHOLD",
					adjust_threshold=True,
					nugget_pipeline=Pipeline(
						[
							ContextSentenceCacher(),
							CopyNormalizer(),
							OntoNotesLabelParaphraser(),
							SplitAttributeNameLabelParaphraser(do_lowercase=True, splitters=[" ", "_"]),
							SBERTLabelEmbedder("SBERTBertLargeNliMeanTokensResource"),
							SBERTTextEmbedder("SBERTBertLargeNliMeanTokensResource"),
							BERTContextSentenceEmbedder("BertLargeCasedResource"),
							RelativePositionEmbedder()
						]
					),
					find_additional_nuggets=find_additional_nuggets
				)
			]
		)

		# run matching phase
		def status_callback_fn(message, progress):
			status.update(progress, message)
			self.update_state(state=status.state, meta=status.meta)

		status_callback = StatusCallback(status_callback_fn)

		def interaction_callback_fn(pipeline_element_identifier, feedback_request):
			feedback_request["identifier"] = pipeline_element_identifier

			a = RedisCache.Redis_Cache_Manager
			redis_client = a.user(1).redis_client
			redis_client.set(f"{userid}:feedback_request", json.dumps(feedback_request))
			try:
				feedback_cond.wait(feedback_mutex)
			finally:
				feedback_mutex.unlock()
			return feedback

		interaction_callback = InteractionCallback(interaction_callback_fn)
		matching_phase(document_base, interaction_callback, status_callback, statistics)
		document_base_to_ui.emit(document_base)
		finished.emit("Finished!")
	except Exception as e:
		error_callback.emit(str(e))


def find_additional_nuggets(nugget, documents):
	new_nuggets = []
	for document in documents:
		doc_text = document.text.lower()
		nug_text = nugget.text.lower()
		start = 0
		while True:
			start = doc_text.find(nug_text, start)
			if start == -1:
				break
			else:
				new_nuggets.append((document, start, start + len(nug_text)))
				start += len(nug_text)
	return new_nuggets
