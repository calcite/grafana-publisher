=================
Grafana Publisher
=================

This is a simple utility that helps maintaining two Grafana instances in a
selective sync.

It makes sense in a following setup:

* You want to have a public (or private but with a single layer user privileges)
  Grafana dashboard server, but you don't want to allow users to edit
  the dashboards.
* Also, you want this public server setup to be 100% scriptable, so
  it's dashboard are stored in a repository along with the setup script
  (typically Ansible). The server can then periodically pull the repo with the
  dashboard folder to keep the dashboards up-to-date.
* To allow dashboard creation, you set-up a second Grafana server (a sandbox
  server) that is private with single layer of user privileges, where any
  logged-in user can develop their dashboards.
* When a user develops a sensible dashboard on the sandbox server, you want to
  publish this dashboard on the public server. This is where Grafana Publisher
  comes in.

Grafana publisher scans a Grafana instance (the sanbox server) for dashboards
tagged with a selected keyword (default: ``Published``), and then looks
for versions that contains a selected phrase (default: ``Publish``)
and commits those dashboards to the public server's dashboard repository.
From there, the dashboards will eventually get pulled and updated in the public
server.

Installation
------------

Docker container
++++++++++++++++

The most logical way to run this script is in a time-scheduled CI job
(as Grafana does not have webhooks for dashboard-editing events). For that
reason, a Dockerfile_ is provided so you can build a Docker container that
you can run with configuration environment variables.

Manual install
++++++++++++++

Poetry_ install (from repo)::

    $ git clone https://github.com/calcite/grafana-publisher.git
    $ cd grafana-publisher
    $ poetry install


Usage
-----

Grafana publisher works as follows:

* If the target repository that stores target Grafana dashboard definitions
  is Gitlab hosted, it checks the repository's last commit date via GitLab API.
* It checks the source Grafana instance for new versions of tagged dashboards
  and looks for versions with defined keyword or key-phrase in the
  version message:

  * The default keyword is ``Publish``
  * The default keyphrase is ``Publish: <some commit message>``. If this format
    is used, the commit message is propagated into the target repository commit
    message.
* If no new versions are detected at the source Grafana instance, Grafana
  publisher exits.
* If new versions of dashboards tagged for publishing are available, those are
  copied into the target repository (maintaining folder structure of the source
  Grafana instance.
* Target repository is comitted and pushed.

There are two basic ways how to use Grafana publisher:

1. Everything, including the git tasks on the target repository
   (cloning, committing, pushing), is done by Grafana publisher.
   This method is useful when Grafana publisher is run as as a standalone
   service.
2. The target repository is provided as working directory, Grafana publisher
   takes care of the update (checking with source Grafana instance, updating the
   new dashboard versions), but the git tasks with the target repository are
   are done separately.
   This method is useful when Grafan publisher is run as part of a CI process
   on a pre-existing working directory structure of the target repo.

Selection of method is done via configuration.

Configuration
+++++++++++++

Grafana publisher uses Onacol_ as the configuration library, that means that
it can be configured via YAML config file, command-line parameters, environment
variables or a combination thereof.

Basic configuration is listed in the example config file, generated with command
``grafana_publisher --get-config-template test_config.yaml``:

.. code-block:: yaml

    grafana_src:
      api_token:  # Grafana API access token (Generate in your grafana instance, must be "Editor" level)
      url:  # Root URL of your grafana instance.
      published_tag: Published # Tag that marks tracked dashboards
      publish_message: Publish # Tag that marks dashboard versions that shall be published.
    target_repo:
      repo_url: ''  # Target repository URL. Use "local" for work on local repo.
      clone_path: .  # Directory path to which the target repo is/will be cloned.
      dashboard_path:  # Directory path within the target repo that contains the dashboard folder/file structure.
      branch: master # Which branch on the target repo should be used to commit updates.
      commit_and_push: true # Whether commit and push to the target repo should be done by the Grafana Publisher.
      commit_log_file:  # If set, the human-readable update summary will be output to a file.
      gitlab:   # If the target repo is on Gitlab instance, it's API can be used to check the update status without cloning.
        url:    # URL of the Gitlab instance storing the target repo.
        access_token:  # Access token for the Gitlab repo.
        project_id:  # Project ID for the repo on the Gitlab instance.
    general:
      log_level: INFO # Logging level (use Python logging values - DEBUG, INFO, WARNING, ERROR, CRITICAL)

To use Grafana publisher in the way described above as method 2 (git operations
are done by external script), use ``target_repo:repo_url: "local"``.

Using configuration file, the Grafana publisher is run in a following way::

    $ grafana_publisher --config <your_config_file.yaml>

For configuration via environment variables, see this example Gitlab CI
definition:

.. code-block:: yaml

    variables:
      PUBLISHER_USER_NAME: Grafana Publisher
      PUBLISHER_EMAIL: Grafana.Publisher@noemail.invalid
      GRAFPUB_GRAFANA_SRC__URL: <source grafana URL>
      GRAFPUB_GRAFANA_SRC__API_TOKEN: <source grafana API TOKEN>
      GRAFPUB_TARGET_REPO__REPO_URL: local
      GRAFPUB_TARGET_REPO__DASHBOARD_PATH: General
      GRAFPUB_TARGET_REPO__COMMIT_AND_PUSH: 'false'
      GRAFPUB_TARGET_REPO__COMMIT_LOG_FILE: update-log.txt

    stages:
      - load

    copy_from_sandbox:
      stage: load
      image: <your docker image with grafana_publisher>
      before_script:
        - git config user.email "${PUBLISHER_USER_NAME}"
        - git config user.name "${PUBLISHER_EMAIL}"
        - git remote set-url origin <your target repo>
        - git checkout master
        - git pull
      script:
        - grafana_publisher
        # In case of no changes, exit
        - '[ ! -f ${GRAFPUB_TARGET_REPO__COMMIT_LOG_FILE} ] && echo "No changes detected, skipping the rest." && echo "skipped" > .runner-result && exit 0'
        # Otherwise, commit and push
        - 'git add "${GRAFPUB_TARGET_REPO__DASHBOARD_PATH}/*"'
        - git commit -F ${GRAFPUB_TARGET_REPO__COMMIT_LOG_FILE}
        - git push
      after_script:
        - rm -f ${GRAFPUB_TARGET_REPO__COMMIT_LOG_FILE}
      rules:
        - when: manual
      allow_failure: true
      tags:
        - internal

Note that environment variables starting with prefix ``GRAFPUB`` are matching the
configuration settings described in the configuration file. See Onacol_ for
details on this configuration method.

.. _`JNevrly/cookiecutter-pypackage-poetry`: https://github.com/JNevrly/cookiecutter-pypackage-poetry
.. _Dockerfile: Dockerfile
.. _Onacol: https://github.com/calcite/onacol
.. _Poetry: https://python-poetry.org/
