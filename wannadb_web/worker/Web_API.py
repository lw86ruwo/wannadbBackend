import csv
import json
import logging
import os
from typing import Optional

from celery import Celery,Task

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
from wannadb_web.SQLite import Cache_DB
from wannadb_web.SQLite.Cache_DB import SQLiteCacheDBWrapper

logger = logging.getLogger(__name__)

# Initialize Celery
celery = Celery('tasks', broker=os.environ.get("CELERY_BROKER_URL"))


@celery.task(bind=True)
def create_document_base(self, _id: int, documents: [Document], attributes: [Attribute], statistics: [Statistics]):
	logger.debug("Called function 'create_document_base'.")
	sqLiteCacheDBWrapper: Optional[SQLiteCacheDBWrapper] = None
	try:
		sqLiteCacheDBWrapper = Cache_DB.Cache_Manager.user(_id)
		sqLiteCacheDBWrapper.reset_cache_db()

		document_base = DocumentBase(documents, attributes)
		sqLiteCacheDBWrapper.sqLiteCacheDB.create_input_docs_table("input_document", document_base.documents)

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

		#save_document_base_to_bson(document_base, _id)

		return {'current': 100, 'total': 100, 'status': 'Task completed!'}
	except Exception as e:
		error = str(e)
		return error
	finally:
		if sqLiteCacheDBWrapper is not None:
			sqLiteCacheDBWrapper.sqLiteCacheDB.conn.close()


@celery.task(bind=True)
def load_document_base_from_bson(self, path, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'load_document_base_from_bson'.")
	status_callback.emit("Loading document base from BSON...", -1)
	cache_db = None
	try:
		with open(path, "rb") as file:
			document_base = DocumentBase.from_bson(file.read())

			if not document_base.validate_consistency():
				logger.error("Document base is inconsistent!")
				error_callback.emit("Document base is inconsistent!")
				return

			cache_db = reset_cache_db(cache_db)
			for attribute in document_base.attributes:
				cache_db.create_table_by_name(attribute.name)
			cache_db.create_input_docs_table("input_document", document_base.documents)

			document_base_to_ui.emit(document_base)
			finished.emit("Finished!")
	except FileNotFoundError:
		logger.error("File does not exist!")
		error_callback.emit("File does not exist!")
	except Exception as e:
		error_callback.emit(str(e))
	finally:
		if cache_db is not None:
			cache_db.conn.close()


def save_document_base_to_bson(document_base: DocumentBase, _id: int):
	logger.debug("Called function 'save_document_base_to_bson'.")
	try:
		with open(path, "wb") as file:
			file.write(document_base.to_bson())
			document_base_to_ui.emit(document_base)
			finished.emit("Finished!")
	except FileNotFoundError:
		logger.error("Directory does not exist!")
		error_callback.emit("Directory does not exist!")
	except Exception as e:
		error_callback.emit(str(e))


def save_table_to_csv(path, document_base, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'save_table_to_csv'.")
	status_callback.emit("Saving table to CSV...", -1)
	try:
		# check that the table is complete
		for attribute in document_base.attributes:
			for document in document_base.documents:
				if attribute.name not in document.attribute_mappings.keys():
					logger.error("Cannot save a table with unpopulated attributes!")
					error_callback.emit("Cannot save a table with unpopulated attributes!")
					return

		# TODO: currently stores the text of the first matching nugget (if there is one)
		table_dict = document_base.to_table_dict("text")
		headers = list(table_dict.keys())
		rows = []
		for ix in range(len(table_dict[headers[0]])):
			row = []
			for header in headers:
				if header == "document-name":
					row.append(table_dict[header][ix])
				elif table_dict[header][ix] == []:
					row.append(None)
				else:
					row.append(table_dict[header][ix][0])
			rows.append(row)
		with open(path, "w", encoding="utf-8", newline="") as file:
			writer = csv.writer(file, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
			writer.writerow(headers)
			writer.writerows(rows)
		document_base_to_ui.emit(document_base)
		finished.emit("Finished!")
	except FileNotFoundError:
		logger.error("Directory does not exist!")
		error_callback.emit("Directory does not exist!")
	except Exception as e:
		error_callback.emit(str(e))


def add_attribute(name, document_base, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'add_attribute'.")
	status_callback.emit("Adding attribute...", -1)
	try:
		if name in [attribute.name for attribute in document_base.attributes]:
			logger.error("Attribute name already exists!")
			error_callback.emit("Attribute name already exists!")
		elif name == "":
			logger.error("Attribute name must not be empty!")
			error_callback.emit("Attribute name must not be empty!")
		else:
			document_base.attributes.append(Attribute(name))
			document_base_to_ui.emit(document_base)
			finished.emit("Finished!")
	except Exception as e:
		error_callback.emit(str(e))


def add_attributes(names, document_base, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'add_attributes'.")
	status_callback.emit("Adding attributes...", -1)
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
		document_base_to_ui.emit(document_base)
		finished.emit("Finished!")
	except Exception as e:
		error_callback.emit(str(e))


def remove_attribute(name, document_base, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'remove_attribute'.")
	status_callback.emit("Removing attribute...", -1)
	try:
		if name in [attribute.name for attribute in document_base.attributes]:
			for document in document_base.documents:
				if name in document.attribute_mappings.keys():
					del document.attribute_mappings[name]

			for attribute in document_base.attributes:
				if attribute.name == name:
					document_base.attributes.remove(attribute)
					break
			document_base_to_ui.emit(document_base)
			finished.emit("Finished!")
		else:
			logger.error("Attribute name does not exist!")
			error_callback.emit("Attribute name does not exist!")
	except Exception as e:
		error_callback.emit(str(e))


def forget_matches_for_attribute(name, document_base, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'forget_matches_for_attribute'.")
	status_callback.emit("Forgetting matches...", -1)
	try:
		if name in [attribute.name for attribute in document_base.attributes]:
			for document in document_base.documents:
				if name in document.attribute_mappings.keys():
					del document.attribute_mappings[name]
			document_base_to_ui.emit(document_base)
			finished.emit("Finished!")
		else:
			logger.error("Attribute name does not exist!")
			error_callback.emit("Attribute name does not exist!")
	except Exception as e:
		error_callback.emit(str(e))


def forget_matches(document_base, status_callback, error_callback, document_base_to_ui, finished):
	logger.debug("Called function 'forget_matches'.")
	status_callback.emit("Forgetting matches...", -1)
	try:
		for attribute in document_base.attributes:
			document_base.delete_table(attribute.name)
			document_base.create_table_by_name(attribute.name)
		for document in document_base.documents:
			document.attribute_mappings.clear()
		document_base_to_ui.emit(document_base)
		finished.emit("Finished!")
	except Exception as e:
		error_callback.emit(str(e))


def save_statistics_to_json(path, statistics, status_callback, error_callback, finished):
	logger.debug("Called function 'save_statistics_to_json'.")
	status_callback.emit("Saving statistics to JSON...", -1)
	try:
		with open(path, "w", encoding="utf-8") as file:
			json.dump(statistics.to_serializable(), file, indent=2)
			finished.emit("Finished!")
	except FileNotFoundError:
		logger.error("Directory does not exist!")
		error_callback.emit("Directory does not exist!")
	except Exception as e:
		error_callback.emit(str(e))


def interactive_table_population(document_base, statistics, status_callback, error_callback,
								 feedback_request_to_ui, feedback_cond, feedback_mutex,
								 feedback, finished, document_base_to_ui):
	logger.debug("Called function 'interactive_table_population'.")
	try:
		# load default matching phase
		status_callback.emit("Loading matching phase...", -1)
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
			status_callback.emit(message, progress)

		status_callback = StatusCallback(status_callback_fn)

		def interaction_callback_fn(pipeline_element_identifier, feedback_request):
			feedback_request["identifier"] = pipeline_element_identifier
			feedback_request_to_ui.emit(feedback_request)

			feedback_mutex.lock()
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
