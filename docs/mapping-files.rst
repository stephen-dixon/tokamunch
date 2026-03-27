Mapping files
=============

Generate a mapping template from IDS schema paths:

.. code-block:: bash

   munchi init-mapping --ids magnetics --leaves-only

The generated JSON maps each template path to an **annotation stub** — a dict
with a ``"comment"`` key pre-populated from the IDS data dictionary:

.. code-block:: json

   {
     "magnetics/flux_loop[#]/flux/data[#]": {"comment": "Flux [Wb]"},
     "magnetics/flux_loop[#]/position[#]/r": {"comment": "Major radius [m]"},
     "magnetics/b_field_pol_probe[#]/field/data[#]": {"comment": "Data [T]"}
   }

Keys use the **mapping-template path** format (see :doc:`path-syntax`): array
indices are replaced with the placeholder ``[#]``.

Replace a stub value with your mapper expression once you have implemented a
path.  See :doc:`mapping-annotations` for details on the annotation syntax and
the ``munchi update-mapping`` command for adding stubs to an existing file.

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
