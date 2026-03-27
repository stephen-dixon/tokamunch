Path syntax
===========

Concrete runtime path
---------------------

.. code-block:: text

   magnetics/flux_loop[0]/position[0]/r

Array indices (``[N]``) are resolved at runtime by querying the mapper for
array lengths.

Non-concrete IDS/schema path
----------------------------

.. code-block:: text

   magnetics/flux_loop(:)/position(:)/r

``(:)`` marks an array dimension in the IMAS data dictionary schema.  These
paths are used internally and are not passed directly to the mapper.

Mapping-template path
---------------------

.. code-block:: text

   magnetics/flux_loop[#]/position[#]/r

Template paths are used as keys in mapping JSON files.  ``[#]`` is a
placeholder that matches any array index.  Array-struct nodes use ``[#]``
like any other array dimension:

.. code-block:: text

   magnetics/flux_loop(:)  ->  magnetics/flux_loop[#]

Concrete-to-template conversion
--------------------------------

The ``concrete_path_to_template`` function (and the ``--mapping`` CLI option)
converts a concrete runtime path back to its template form by replacing every
``[N]`` index with ``[#]``:

.. code-block:: text

   magnetics/flux_loop[0]/position[2]/r
   ->  magnetics/flux_loop[#]/position[#]/r

This conversion is used by ``map --mapping`` to intersect expanded paths with
the keys defined in a mapping file.
