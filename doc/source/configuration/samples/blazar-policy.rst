==================
Sample Policy File
==================

.. warning::

   Using a JSON-formatted policy file is deprecated since Blazar 7.0.0
   (Wallaby).  This `oslopolicy-convert-json-to-yaml`__ tool will migrate your
   existing JSON-formatted policy file to YAML in a backward-compatible way.

.. __: https://docs.openstack.org/oslo.policy/latest/cli/oslopolicy-convert-json-to-yaml.html

The following is a sample blazar policy file for adaptation and use.

The sample policy can also be viewed in :download:`file form
</_static/blazar.policy.yaml.sample>`.

.. important::

   The sample policy file is auto-generated from blazar when this
   documentation is built. You must ensure your version of blazar matches
   the version of this documentation.

.. literalinclude:: /_static/blazar.policy.yaml.sample
