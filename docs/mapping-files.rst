Mapping files
=============

Generate a blank mapping template from IDS schema paths:

.. code-block:: bash

   munchi init-mapping --ids magnetics --leaves-only

The generated JSON maps each template path to an empty object:

.. code-block:: json

   {
     "magnetics/flux_loop[#]/field": {},
     "magnetics/b_field_pol_probe[#]/field": {}
   }

Keys use the **mapping-template path** format (see :doc:`path-syntax`): array
indices are replaced with the placeholder ``[#]``.

Restricting a mapping run to a file's keys
------------------------------------------

Pass ``--mapping`` to ``map`` to run only the paths whose template form appears
as a key in the mapping file:

.. code-block:: bash

   munchi map --ids magnetics --mapping my_mapping.json

This computes the intersection of the fully-expanded concrete IDS paths and the
keys defined in the file.  Paths with no corresponding mapping key are skipped
without error.  Combine with ``--leaves-only`` to restrict expansion to scalar
fields first, reducing unnecessary array-length queries:

.. code-block:: bash

   munchi map --ids magnetics --leaves-only --mapping my_mapping.json

.. note::

   Command options are documented in :doc:`cli`.
