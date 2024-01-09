from typing import Dict, Optional
import logging

from wannadb_web.Redis.util import connectRedis

logger = logging.getLogger(__name__)

Redis_Cache_Manager: Optional["RedisCacheManager"] = None


class RedisCacheManager:
	def __init__(self) -> None:
		"""Initialize the RedisCacheManager manager."""
		global Redis_Cache_Manager
		if Redis_Cache_Manager is not None:
			logger.error("There can only be one RedisCacheManager!")
			assert False, "There can only be one RedisCacheManager!"
		else:
			Redis_Cache_Manager = self

		self._resources: Dict[str, RedisCache] = {}
		self.redis_client = connectRedis()

		logger.info("Initialized the RedisCacheManager.")

	def user(self, user_id: str) -> "RedisCache":
		"""Get or create a user-specific RedisCache instance."""
		if user_id not in self._resources:
			self._resources[user_id] = RedisCache(self.redis_client, user_id)
		return self._resources[user_id]

	def __enter__(self) -> "RedisCacheManager":
		"""Enter the RedisCacheManager context."""
		logger.info("Entered the RedisCacheManager.")
		return self

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		"""Exit the RedisCacheManager context."""
		logger.info("Kill all Redis connections")
		for resource in self._resources.values():
			resource.close()

		logger.info("Exited the resource manager.")


class RedisCache:
	def __init__(self, redis_client, user_id: str) -> None:
		"""Initialize the RedisCache instance for a specific user."""
		self.redis_client = redis_client
		self.user_space_key = f"user:{user_id}"

	def set(self, key: str, value: str) -> None:
		"""Set a key-value pair in the user-specific space."""
		user_key = f"{self.user_space_key}:{key}"
		self.redis_client.set(user_key, value)

	def get(self, key: str) -> Optional[str]:
		"""Get the value associated with a key in the user-specific space."""
		user_key = f"{self.user_space_key}:{key}"
		return self.redis_client.get(user_key)

	def close(self) -> None:
		"""Close the Redis connection for the user-specific space."""
		self
		pass
