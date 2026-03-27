Mapping file annotations
========================

Mapping files support **comment stubs** — path entries whose value is a dict
with a ``"comment"`` key rather than a mapper expression.  They serve as
structured documentation inside the mapping file and are treated as *stubs*:
paths that exist in the schema but have not yet been implemented.

Syntax
------

A minimal stub:

.. code-block:: json

   {
     "magnetics/flux_loop[#]/field": {"comment": ""},
     "magnetics/b_field_pol_probe[#]/field": {"comment": "Hall probe B-field"}
   }

Extended form — all allowed keys:

.. code-block:: json

   {
     "magnetics/flux_loop[#]/field": {
       "comment": "flux loop field from UDA raw channel",
       "units": "T",
       "source": "AMC_FLUX_LOOP_{i}"
     }
   }

Only ``"comment"``, ``"units"``, and ``"source"`` are recognised annotation
keys.  Any dict containing ``"comment"`` *and only* those keys is treated as
a stub; any other key combination is forwarded to the mapper as a normal
mapping value.

``init-mapping`` generates stubs
---------------------------------

``munchi init-mapping`` now generates stubs instead of empty objects, giving
you a template ready to annotate:

.. code-block:: bash

   munchi init-mapping --ids magnetics --leaves-only --output magnetics.json

Output excerpt:

.. code-block:: json

   {
     "magnetics/flux_loop[#]/field": {"comment": ""},
     "magnetics/flux_loop[#]/position[#]/phi": {"comment": ""},
     "magnetics/b_field_pol_probe[#]/field": {"comment": ""}
   }

Adding stubs for missing paths
-------------------------------

As the IDS schema evolves, new paths may appear that are not yet in your
mapping file.  Use ``munchi update-mapping`` to add stubs for those paths
while preserving all existing entries:

.. code-block:: bash

   munchi update-mapping --ids magnetics --mapping magnetics.json

This is a non-destructive operation: existing paths, including their comments
and mapper expressions, are never modified.  Only paths absent from the file
gain a new ``{"comment": ""}`` entry.  Write to a new file with ``--output``:

.. code-block:: bash

   munchi update-mapping --ids magnetics --mapping magnetics.json \
       --output magnetics-updated.json

Use ``--force`` to overwrite the output file if it already exists, and
``--leaves-only`` to restrict the stub generation to leaf (scalar) paths.

Interaction with ``--mapping`` filter
--------------------------------------

When you run ``munchi map --mapping magnetics.json``, stub entries are
**skipped** — they are included in the key intersection used for path
selection, but because their value is a comment dict the mapper is never
called for them.  This means you can ship a partially-annotated file and
only live paths will be evaluated:

.. code-block:: bash

   # Paths with real mapper expressions are evaluated.
   # Stub paths are silently skipped.
   munchi map --ids magnetics --mapping magnetics.json --output results.json

Library usage
-------------

.. code-block:: python

   from tokamunch.templates import (
       is_comment_stub,
       merge_mapping_stubs,
       build_blank_mapping_template,
   )

   # Check whether a mapping value is an annotation stub.
   is_comment_stub({"comment": "flux loop field"})  # True
   is_comment_stub({"comment": "", "units": "T"})   # True
   is_comment_stub({})                               # False
   is_comment_stub("raw_channel_name")              # False

   # Generate a mapping template with stubs.
   template = build_blank_mapping_template("magnetics", leaves_only=True)

   # Add stubs for any paths in the schema not already in an existing file.
   merge_mapping_stubs("magnetics", "magnetics.json", leaves_only=True)
