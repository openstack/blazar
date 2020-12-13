========
Policies
========

.. warning::

   Using a JSON-formatted policy file is deprecated since Blazar 7.0.0
   (Wallaby).  This `oslopolicy-convert-json-to-yaml`__ tool will migrate your
   existing JSON-formatted policy file to YAML in a backward-compatible way.

.. __: https://docs.openstack.org/oslo.policy/latest/cli/oslopolicy-convert-json-to-yaml.html

The following is an overview of all available policies in Blazar. For a sample
configuration file, refer to :doc:`/configuration/samples/blazar-policy`.

To change policies, please create a policy file in */etc/blazar/* and specify
the policy file name at the *oslo_policy/policy_file* option in *blazar.conf*.

.. show-policy::
   :config-file: etc/blazar/blazar-policy-generator.conf
