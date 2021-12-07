# -*- coding: utf-8 -*-
"""
.. module: grafana_publisher.grafana_publisher
   :synopsis: Main module
.. moduleauthor:: "Josef Nevrly <jnevrly@alps.cz>"
"""

import logging
import pathlib
import json

from pathvalidate import sanitize_filename, sanitize_filepath

from .utils import GrafanaApiUtils, TargetRepoUtils, \
    GrafanaPublisherResourceNotFoundError


logger = logging.getLogger(__name__)


def publish_dashboards(config):
    grafana_api = GrafanaApiUtils(config['grafana_src'])
    target_repo = TargetRepoUtils(config['target_repo'])

    if target_repo.gitlab_enabled:
        last_target_update = target_repo.get_last_commit_date()
    else:
        last_target_update = None

    # Check if there are new versions
    updated_dashboards = []
    for dash in grafana_api.get_published_ids():
        try:
            logger.info("Checking dashboard %s (ID: %d):", dash['title'],
                        dash['id'])
            dashboard_version = grafana_api.last_published_version(
                dash["id"], since_date=last_target_update
            )
            updated_dashboards.append((dash, dashboard_version))
        except GrafanaPublisherResourceNotFoundError:
            continue

    if updated_dashboards:
        logger.info("Dashboards to update: %d", len(updated_dashboards))
        # Make sure the target repository is present and up-to date
        # (clone/pull if not)
        target_repo.assert_git()

        # List to track changes
        change_list = []

        for dashboard_metadata, dashboard in updated_dashboards:
            target_version, target_path = target_repo.get_dashboard(
                dashboard_metadata["uid"])
            if target_path is None:
                logger.info("Dashboard %s not present in target, creating",
                            dashboard["data"]["title"])
                # Create new file/path
                folder_path = pathlib.Path(
                    target_repo.dash_root,
                    sanitize_filepath(dashboard_metadata["folderTitle"])
                )
                folder_path.mkdir(parents=True, exist_ok=True)

                target_path = pathlib.Path(
                    folder_path,
                    f"{sanitize_filename(dashboard['data']['title']).lower().replace(' ', '_')}.json"
                )
            elif target_version == dashboard["version"]:
                logger.info("Dashboard %s is up to date, skipping.",
                            dashboard["data"]["title"])
                continue
            elif target_version > dashboard["version"]:
                logger.warning(
                    "Target dashboard %s is bigger version (%d) than the "
                    "source version (%d) - skipping.",
                    dashboard["data"]["title"], target_version,
                    dashboard["version"])
                continue

            # Update file
            logger.info("Updating dashboard %s ...", dashboard["data"]["title"])
            with target_path.open(mode="w") as dash_file:
                json.dump(
                    dashboard["data"], dash_file, indent=2, sort_keys=True)
            change_list.append(
                (dashboard["data"]["title"],
                 grafana_api.get_publish_msg(dashboard["message"]))
            )

        if change_list:
            target_repo.commit(change_list)
            target_repo.push()

        logger.info("Done. %d dashboards updated.", len(change_list))

    else:
        logger.info("No dashboards need to be updated.")
