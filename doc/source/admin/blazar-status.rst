=============
blazar-status
=============

Synopsis
========

::

  blazar-status <category> <command> [<args>]

Description
===========

:program:`blazar-status` is a tool that provides routines for checking the
status of a Blazar deployment.

Options
=======

The standard pattern for executing a :program:`blazar-status` command is::

    blazar-status <category> <command> [<args>]

Run without arguments to see a list of available command categories::

    blazar-status

Categories are:

* ``upgrade``

Detailed descriptions are below.

You can also run with a category argument such as ``upgrade`` to see a list of
all commands in that category::

    blazar-status upgrade

These sections describe the available categories and arguments for
:program:`blazar-status`.

Upgrade
~~~~~~~

.. _blazar-status-checks:

``blazar-status upgrade check``
  Performs a release-specific readiness check before restarting services with
  new code. This command expects to have complete configuration and access
  to databases and services.

  **Return Codes**

  .. list-table::
     :widths: 20 80
     :header-rows: 1

     * - Return code
       - Description
     * - 0
       - All upgrade readiness checks passed successfully and there is nothing
         to do.
     * - 1
       - At least one check encountered an issue and requires further
         investigation. This is considered a warning but the upgrade may be OK.
     * - 2
       - There was an upgrade status check failure that needs to be
         investigated. This should be considered something that stops an
         upgrade.
     * - 255
       - An unexpected error occurred.

  **History of Checks**

  **3.0.0 (Stein)**

  * Placeholder to be filled in with checks as they are added in Stein.
