"""
.. module: grafana_publisher.utils
   :synopsis: Utility classes for handling the grafana and git repos
.. moduleauthor:: "Josef Nevrly <jnevrly@alps.cz>"
"""
import logging
import subprocess
import pathlib
import re
import json
from typing import Dict, Any, List, Union, Tuple

import requests
import arrow

logger = logging.getLogger(__name__)


class GrafanaPublisherError(Exception):
    pass


class GrafanaPublisherResourceNotFoundError(GrafanaPublisherError):
    pass


class GrafanaApiUtils:

    def __init__(self, config: Dict):
        self._config = config
        self._src_headers = {}
        if self._config["api_token"]:
            self._src_headers["Authorization"] = \
                f"Bearer {self._config['api_token']}"
        self.PUBLISH_MSG = self._config["publish_message"]
        self.PUBLISH_PATTERN = re.compile(f"{self.PUBLISH_MSG}:(.*)")

    @staticmethod
    def _get_json(url: str, headers: Dict[str, str]) -> Any:
        req = requests.get(url, headers=headers)
        if req.ok:
            return req.json()
        else:
            if req.status_code == 404:
                raise GrafanaPublisherResourceNotFoundError(
                    f"Resource not found: {url}")
            else:
                raise GrafanaPublisherError(
                    f"Couldn't get resource from {url}: {req.reason}")

    def url_get(self, api_url: str) -> Any:
        return self._get_json(f"{self._config['url']}/{api_url}",
                              headers=self._src_headers)

    def get_published_ids(self) -> List:
        return self.url_get(f"api/search?tag={self._config['published_tag']}")

    def last_published_version(self,
                               dash_id: int,
                               since_date: Union[arrow.Arrow, None] = None
                               ) -> Any:
        for version in self.url_get(f"api/dashboards/id/{dash_id}/versions"):
            if self.PUBLISH_MSG in version['message']:
                if ((since_date is not None) and
                        (arrow.get(version['created']) < since_date)):
                    logger.info("Version %s skipped (already updated.)",
                                version['version'])
                    continue

                # Get the particular version
                return self.url_get(
                    f"api/dashboards/id/{dash_id}/versions/{version['version']}"
                )
        else:
            logger.info(
                f"Dashboard Id {version['dashboardId']} is tagged for "
                f"publishing, but no new published version is available.")
            raise GrafanaPublisherResourceNotFoundError()

    def get_publish_msg(self, version_msg: str) -> str:
        msg = version_msg.strip()
        m = self.PUBLISH_PATTERN.match(msg)
        if m:
            return m.group(1).strip()
        else:
            if msg == self.PUBLISH_MSG:
                return "Updated"
            else:
                return msg


class TargetRepoUtils:
    GITLAB_API = "api/v4"

    def __init__(self, config: Dict):
        self._config = config
        self.dash_root = pathlib.Path(self._config["clone_path"],
                                      self._config["dashboard_path"])
        self.gitlab_enabled = bool(self._config["gitlab"]["url"])
        self._gitlab_header = {}
        if self._config["gitlab"]["access_token"]:
            self._gitlab_header["PRIVATE-TOKEN"] = \
                self._config["gitlab"]["access_token"]

        self.local_repo = (self._config["repo_url"].lower() == "local")

    def _run_cmd(self, cmd: List, description: str, cwd:str = None) -> str:
        if cwd is None:
            cwd = self._config["clone_path"]
        res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise GrafanaPublisherError(
                f"{description} failed: {res.stderr.decode('utf-8').strip()}")
        else:
            logging.info("%s: OK", description)
            return res.stdout.decode("utf-8").strip()

    def get_dashboard(self,
                      dash_uid: str
                      ) -> Tuple[Union[str, None], Union[str, None]]:
        for path in self.dash_root.glob("**/*.json"):
            with open(path, "r") as dash_file:
                dash = json.load(dash_file)
                if dash['uid'] == dash_uid:
                    return dash['version'], path
        else:
            return None, None

    def _gitlab_get(self, api_url: str) -> Any:
        url = f"{self._config['gitlab']['url']}/{self.GITLAB_API}/{api_url}"
        req = requests.get(url, headers=self._gitlab_header)
        if req.ok:
            return req.json()
        else:
            if req.status_code == 404:
                raise GrafanaPublisherResourceNotFoundError(
                    f"Target repo resource not found: {url}")
            else:
                raise GrafanaPublisherError(
                    f"Counld't get resource from "
                    f"target repo {url}: {req.reason}"
                )

    def assert_git(self) -> None:
        if self.local_repo:
            # Just make sure the clone_path actually is a repo
            self._run_cmd(["git", "status"], "Checking if target repo exist")
        else:
            try:
                remote_url = self._run_cmd(
                    ["git", "config", "--get", "remote.origin.url"],
                    "Getting remote URL")
                if remote_url != self._config["repo_url"]:
                    # Repo exists, but the remote is different - abort
                    raise GrafanaPublisherError(
                        f"Target repository has a different "
                        f"remote URL: {remote_url}")
                # Make sure to switch to master and pull for the last version
                self._run_cmd(
                    ["git", "checkout", self._config["branch"]],
                    f"Checking out the branch {self._config['branch']}"
                )
                self._run_cmd(["git", "pull"], f"Pulling the latest version")
            except FileNotFoundError:
                # Git repo is not cloned yet
                logging.info("Target repository not found -> need to clone.")
                self._run_cmd(
                    ["git", "clone", self._config["repo_url"],
                     self._config["clone_path"]],
                    f"Cloning the target repository "
                    f"to {self._config['clone_path']}",
                    cwd="."
                )

    def prepare_commit_msg(self, change_list: List[Tuple[str, str]]) -> str:
        if len(change_list) == 1:
            summary = change_list[0][0]
        else:
            summary = f"{len(change_list)} dashboards"
        commit_msg = f"Published updates to {summary}.\n\n"

        commit_msg += "\n".join(
            [f"{dash}: {update_msg}\n" for dash, update_msg in change_list])
        return commit_msg

    def commit(self, change_list: List[Tuple[str, str]]) -> None:
        self._run_cmd(["git", "add", "-A"], "Staging updates")
        commit_msg = self.prepare_commit_msg(change_list)
        self._run_cmd(["git", "commit", "-m", commit_msg], "Comitting updates")

    def push(self) -> None:
        self._run_cmd(["git", "push"], "Pushing updates")

    def get_last_commit(self) -> Dict:
        return self._gitlab_get(
            f"projects/{self._config['gitlab']['project_id']}/repository/commits/{self._config['branch']}")

    def get_last_commit_date(self) -> arrow.Arrow:
        last_commit = self.get_last_commit()
        return arrow.get(last_commit['created_at'])
