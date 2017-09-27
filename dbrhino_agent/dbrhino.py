import requests
from .__version__ import __version__


class Grant(object):
    def __init__(self, *, id, database, username, version, statements=[],
                 password=None, revoke=False, **kwargs):
        self.id = id
        self.database = database
        self.username = username
        self.statements = statements
        self.version = version
        self.password = password
        self.revoke = revoke


class GrantResult(object):
    NO_CHANGE = "no_change"
    APPLIED = "applied"
    NO_PASSWORD = "no_user_password"
    UNKNOWN_ERROR = "unknown_error"
    REVOKED = "revoked"


class DbRhino(object):
    def __init__(self, config):
        self.config = config

    def _build_headers(self, headers):
        heads_ = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + self.config.access_token,
        }
        heads_.update(headers)
        return heads_

    def _request(self, method, path, headers={}, params={}, **kwargs):
        headers_ = self._build_headers(headers)
        resp = requests.request(method, self.config.remote_url(path),
                                headers=headers_, params=params, **kwargs)
        resp.raise_for_status()
        return resp

    def upsert_databases(self):
        payload = [{"name": db.name, "dbtype": db.dbtype}
                   for db in self.config.databases.values()]
        self._request("PUT", "/api/databases", json=payload)

    def fetch_grants(self):
        return self._request("GET", "/api/grants").json()

    def checkin(self, applied_grants):
        payload = {"applied_grants": applied_grants,
                   "agent_version": __version__}
        return self._request("POST", "/api/agents/checkin", json=payload)
