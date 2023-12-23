import csv
import json
import logging
import traceback
from enum import Enum

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
from wannadb.resources import ResourceManager
from wannadb.statistics import Statistics
from wannadb.status import StatusCallback
from wannadb_parsql.cache_db import SQLiteCacheDB

logger = logging.getLogger(__name__)





class Web_API:
	def __init__(self,):
		super()
		self.cache_db_to_ui = None
		self.error = None
		self.feedback = None
		self.cache_db = None
		logger.info("Initialized WannaDBWebAPI.")

	def _reset_cache_db(self):
		logger.info("Reset cache db")
		if self.cache_db is not None:
			self.cache_db.conn.close()
			self.cache_db = None
		self.cache_db = SQLiteCacheDB(db_file=":memory:")

	def _handle_exception(self, exception):
		traceback.print_exception(type(exception), exception, exception.__traceback__)
		logger.error(str(exception))
		self.error = (str(exception))

	def create_document_base(self, documents: list[Document], attributes: list[Attribute], statistics:Statistics):
		logger.debug("Called slot 'create_document_base'.")
		try:

			self._reset_cache_db()

			document_base = DocumentBase(documents, attributes)
			self.cache_db.create_input_docs_table("input_document", document_base.documents)

			if not document_base.validate_consistency():
				logger.error("Document base is inconsistent!")
				self.error = "Document base is inconsistent!"
				return

			# load default preprocessing phase

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

			# run preprocessing phase
			def status_callback_fn(message, progress):
				self.error = (message, progress)

			status_callback = StatusCallback(status_callback_fn)

			preprocessing_phase(document_base, EmptyInteractionCallback(), status_callback, statistics)
		except FileNotFoundError:
			logger.error("Directory does not exist!")
			self.error = "Directory does not exist!"
		except Exception as e:
			self._handle_exception(e)

	def load_document_base_from_bson(self, path):
		logger.debug("Called slot 'load_document_base_from_bson'.")
		self.status.emit("Loading document base from BSON...", -1)
		try:
			with open(path, "rb") as file:
				document_base = DocumentBase.from_bson(file.read())

				if not document_base.validate_consistency():
					logger.error("Document base is inconsistent!")
					self.error.emit("Document base is inconsistent!")
					return

				self._reset_cache_db()
				for attribute in document_base.attributes:
					self.cache_db.create_table_by_name(attribute.name)
				self.cache_db.create_input_docs_table("input_document", document_base.documents)

				self.document_base_to_ui.emit(document_base)
				self.finished.emit("Finished!")
		except FileNotFoundError:
			logger.error("File does not exist!")
			self.error.emit("File does not exist!")
		except Exception as e:
			self._handle_exception(e)

	def save_document_base_to_bson(self, path, document_base):
		logger.debug("Called slot 'save_document_base_to_bson'.")
		self.status.emit("Saving document base to BSON...", -1)
		try:
			with open(path, "wb") as file:
				file.write(document_base.to_bson())
				self.document_base_to_ui.emit(document_base)
				self.finished.emit("Finished!")
		except FileNotFoundError:
			logger.error("Directory does not exist!")
			self.error.emit("Directory does not exist!")
		except Exception as e:
			self._handle_exception(e)

	def save_table_to_csv(self, path, document_base):
		logger.debug("Called slot 'save_table_to_csv'.")
		self.status.emit("Saving table to CSV...", -1)
		try:
			# check that the table is complete
			for attribute in document_base.attributes:
				for document in document_base.documents:
					if attribute.name not in document.attribute_mappings.keys():
						logger.error("Cannot save a table with unpopulated attributes!")
						self.error.emit("Cannot save a table with unpopulated attributes!")
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
			self.document_base_to_ui.emit(document_base)
			self.finished.emit("Finished!")
		except FileNotFoundError:
			logger.error("Directory does not exist!")
			self.error.emit("Directory does not exist!")
		except Exception as e:
			self._handle_exception(e)

	def add_attribute(self, name, document_base):
		logger.debug("Called slot 'add_attribute'.")
		self.status.emit("Adding attribute...", -1)
		try:
			if name in [attribute.name for attribute in document_base.attributes]:
				logger.error("Attribute name already exists!")
				self.error.emit("Attribute name already exists!")
			elif name == "":
				logger.error("Attribute name must not be empty!")
				self.error.emit("Attribute name must not be empty!")
			else:
				document_base.attributes.append(Attribute(name))
				self.cache_db.create_table_by_name(name)
				self.document_base_to_ui.emit(document_base)
				self.finished.emit("Finished!")
		except Exception as e:
			self._handle_exception(e)

	def add_attributes(self, names, document_base):
		logger.debug("Called slot 'add_attributes'.")
		self.status.emit("Adding attributes...", -1)
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
					self.cache_db.create_table_by_name(name)
			self.document_base_to_ui.emit(document_base)
			self.finished.emit("Finished!")
		except Exception as e:
			self._handle_exception(e)

	def remove_attribute(self, name, document_base):
		logger.debug("Called slot 'remove_attribute'.")
		self.status.emit("Removing attribute...", -1)
		self.cache_db.delete_table(name)
		try:
			if name in [attribute.name for attribute in document_base.attributes]:
				for document in document_base.documents:
					if name in document.attribute_mappings.keys():
						del document.attribute_mappings[name]

				for attribute in document_base.attributes:
					if attribute.name == name:
						document_base.attributes.remove(attribute)
						break
				self.document_base_to_ui.emit(document_base)
				self.finished.emit("Finished!")
			else:
				logger.error("Attribute name does not exist!")
				self.error.emit("Attribute name does not exist!")
		except Exception as e:
			self._handle_exception(e)

	def forget_matches_for_attribute(self, name, document_base):
		logger.debug("Called slot 'forget_matches_for_attribute'.")
		self.status.emit("Forgetting matches...", -1)
		self.cache_db.delete_table(name)
		try:
			if name in [attribute.name for attribute in document_base.attributes]:
				for document in document_base.documents:
					if name in document.attribute_mappings.keys():
						del document.attribute_mappings[name]
				self.cache_db.create_table_by_name(name)
				self.document_base_to_ui.emit(document_base)
				self.finished.emit("Finished!")
			else:
				logger.error("Attribute name does not exist!")
				self.error.emit("Attribute name does not exist!")
		except Exception as e:
			self._handle_exception(e)

	def forget_matches(self, document_base):
		logger.debug("Called slot 'forget_matches'.")
		self.status.emit("Forgetting matches...", -1)
		for attribute in document_base.attributes:
			self.cache_db.delete_table(attribute.name)
			self.cache_db.create_table_by_name(attribute.name)
		try:
			for document in document_base.documents:
				document.attribute_mappings.clear()
			self.document_base_to_ui.emit(document_base)
			self.finished.emit("Finished!")
		except Exception as e:
			self._handle_exception(e)

	def save_statistics_to_json(self, path, statistics):
		logger.debug("Called slot 'save_statistics_to_json'.")
		self.status.emit("Saving statistics to JSON...", -1)
		try:
			with open(path, "w", encoding="utf-8") as file:
				json.dump(statistics.to_serializable(), file, indent=2)
				self.finished.emit("Finished!")
		except FileNotFoundError:
			logger.error("Directory does not exist!")
			self.error.emit("Directory does not exist!")
		except Exception as e:
			self._handle_exception(e)

	def interactive_table_population(self, document_base, statistics):
		logger.debug("Called slot 'interactive_table_population'.")
		try:
			# load default matching phase
			self.status.emit("Loading matching phase...", -1)

			# TODO: this should not be implemented here!
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
				self.status.emit(message, progress)

			status_callback = StatusCallback(status_callback_fn)

			def interaction_callback_fn(pipeline_element_identifier, feedback_request):
				feedback_request["identifier"] = pipeline_element_identifier
				self.feedback_request_to_ui.emit(feedback_request)

				self.feedback_mutex.lock()
				try:
					self.feedback_cond.wait(self.feedback_mutex)
				finally:
					self.feedback_mutex.unlock()

				return self.feedback

			interaction_callback = InteractionCallback(interaction_callback_fn)

			matching_phase(document_base, interaction_callback, status_callback, statistics)

			self.document_base_to_ui.emit(document_base)
			self.statistics_to_ui.emit(statistics)
			self.finished.emit("Finished!")
		except Exception as e:
			self._handle_exception(e)
