from typing import Dict, Optional
import logging

from wannadb_parsql.cache_db import SQLiteCacheDB

logger = logging.getLogger(__name__)

Cache_Manager: Optional["CacheManager"] = None


class CacheManager:
	def __init__(self) -> None:
		"""Initialize the CacheManager manager."""
		global Cache_Manager
		if Cache_Manager is not None:
			logger.error("There can only be one CacheManager!")
			assert False, "There can only be one CacheManager!"
		else:
			Cache_Manager = self

		self._resources: Dict[int, SQLiteCacheDBWrapper] = {}

		logger.info("Initialized the CacheManager.")

	def __enter__(self) -> "CacheManager":
		"""
		Enter the CacheManager context.

		:return: the CacheManager itself
		"""
		logger.info("Entered the CacheManager.")
		return self

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		"""Exit the CacheManager context."""
		logger.info("kill all Redis connections")

		logger.info("Exited the resource manager.")

	def user(self, user_id: int, db_file="wannadb_cache.db") -> "SQLiteCacheDBWrapper":
		"""Get or create a user-specific SQLiteCacheDB instance."""
		if user_id not in self._resources and self._resources[user_id] is None:
			self._resources[user_id] = SQLiteCacheDBWrapper(user_id, db_file)
		return self._resources[user_id]

	def remove_user(self, user_id: int) -> None:
		"""Remove a user from the CacheManager."""
		if user_id in self._resources:
			self._resources[user_id].delete()
			del self._resources[user_id]


class SQLiteCacheDBWrapper:
	def __init__(self, user_id: int, db_file="wannadb_cache.db"):
		"""Initialize the RedisCache instance for a specific user."""
		self.db_identifier = f"{db_file}_{user_id}"
		self.sqLiteCacheDB = SQLiteCacheDB(db_file=self.db_identifier)

	def delete(self):
		self.sqLiteCacheDB.conn.close()
		self.sqLiteCacheDB = None
		self.db_identifier = None

	def reset_cache_db(self):
		logger.debug("Reset cache db")
		if self.sqLiteCacheDB is not None:
			self.sqLiteCacheDB.conn.close()
			self.sqLiteCacheDB = None
		self.sqLiteCacheDB = SQLiteCacheDB(db_file=self.db_identifier)
