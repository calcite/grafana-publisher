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
tagged with a selected keyword (default: ``Publish``), and then looks
for versions that contains a selected phrase (default ``Published``)
and commits those dashboards to the public server's dashboard repository.
From there, the dashboards will eventually get pulled and updated in the public
server.

Installation and usage
----------------------

The most logical way to run this script is in a time-scheduled CI job
(as Grafana does not have webhooks for dashboard-editing events). For that
reason, this utility is provided in the form of a Docker container that
you can run with configuration environment variables.

Installation:
-------------

.. code-block:: console

    $ pip install grafana_publisher

Features
--------

* TODO

.. _`JNevrly/cookiecutter-pypackage-poetry`: https://github.com/JNevrly/cookiecutter-pypackage-poetry
