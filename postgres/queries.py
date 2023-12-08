import bcrypt
from flask import jsonify
from psycopg2 import sql
from postgres.util import execute_query


def getUserID(user: str):
	select_query = sql.SQL("SELECT id FROM users WHERE username = %s;")
	return execute_query(select_query, (user,))


def getOrganisationID(organisation_name: str):
	select_query = sql.SQL("SELECT id FROM organisations WHERE name = %s;")
	return execute_query(select_query, (organisation_name,))


def getMemberIDsFromOrganisationID(organisationID: int):
	select_query = sql.SQL("SELECT userid FROM membership WHERE organisationid = %s;")
	return execute_query(select_query, (organisationID,))


def getOrganisationIDsFromUserId(userID: int):
	select_query = sql.SQL("SELECT organisationid FROM membership WHERE userid = %s;")
	return execute_query(select_query, (userID,))


def checkPassword(user: str, password: str) -> bool:

	select_query = sql.SQL("SELECT password as pw FROM users WHERE username = %s;")
	result = execute_query(select_query, (user,))
	if not result:
		print("checkPassword failed because: \n", "user not found")
		return False
	if len(result) > 1:
		print("checkPassword failed because: \n", "more than 1 user with same name")
		return False
	try:
		if result[0]:
      
			#stored_password = bytes(result[0][0], encoding='utf-8')  # sketchy conversion but works
			stored_password = result[0][0].encode('utf-8')	# i think thats better
			return bcrypt.checkpw(password.encode('utf-8'), stored_password)

		return False

	except Exception as e:
		print("checkPassword failed because: \n", e)
		return False


def checkOrganisationAuthorisation(organisationName: str, userName: str) -> int:
	select_query = sql.SQL("SELECT membership from membership "
						   "where userid == (SELECT id from users where username == (%s)) "
						   "and "
						   "organisationid == (Select id from organisations where name == (%s))")

	result = execute_query(select_query, (organisationName, userName))
	try:
		if result[0]:
			authorisation = result[0]
			return int(authorisation)  # sketchy conversion but works

	except Exception as e:
		print("checkOrganisationAuthorisation failed because: \n", e)
		return 99
