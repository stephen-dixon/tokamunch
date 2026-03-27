Diffing and incremental mapping
================================

``munchi diff``
---------------

Compare two mapping result files (JSON or IMAS HDF5/NetCDF) and print a
human-readable summary of which paths were added, removed, or changed:

.. code-block:: bash

   munchi diff baseline.json updated.json

Output format:

.. code-block:: text

   --- baseline.json
   +++ updated.json

   + magnetics/flux_loop[2]/field           1.23e-03
   - magnetics/b_field_pol_probe[0]/field   4.56e-04
   ~ magnetics/flux_loop[0]/field           7.8e-04 → 7.9e-04

   Summary: 1 added, 1 removed, 1 changed, 42 unchanged

Symbols:

- ``+``  path is new in the second file
- ``-``  path was removed from the first file
- ``~``  path exists in both files but its value changed
- (space) path is identical — hidden by default

Unchanged paths are hidden by default.  To show them:

.. code-block:: bash

   munchi diff baseline.json updated.json --show-unchanged

Restrict the comparison to specific IDS names:

.. code-block:: bash

   munchi diff a.json b.json --ids magnetics equilibrium

``munchi update`` — incremental mapping
----------------------------------------

Map only the paths that are *missing* from an existing result file, then
merge with the existing data and write a new file.  This avoids re-running
the mapper on paths that are already present:

.. code-block:: bash

   # First pass — map what you have now.
   munchi map --ids magnetics --output results.json

   # Later — schema or mapping file changed; fill in the gaps.
   munchi update --input results.json --output results-full.json \
       --ids magnetics

Options:

- ``--mapping FILE``  restrict the missing-path search to keys in a mapping
  file (same semantics as ``munchi map --mapping``)
- ``--config FILE``   path to ``munchi.toml``
- ``--device NAME``   override the device name from config
- ``--set KEY=VALUE`` ad-hoc config overrides (repeatable)

Typical workflow
-----------------

.. code-block:: bash

   # 1. Generate stubs for all leaf paths.
   munchi init-mapping --ids magnetics --leaves-only --output magnetics.json

   # 2. Annotate and implement paths in magnetics.json.

   # 3. Map using the file as a filter.
   munchi map --ids magnetics --mapping magnetics.json --output results.json

   # 4. Compare with a previous run.
   munchi diff results-prev.json results.json

   # 5. Schema updated — add stubs for new paths without losing existing data.
   munchi update-mapping --ids magnetics --mapping magnetics.json \
       --output magnetics-v2.json

   # 6. Incrementally fill in the new paths.
   munchi update --input results.json --output results-v2.json \
       --ids magnetics --mapping magnetics-v2.json

Library usage
-------------

.. code-block:: python

   from tokamunch.diff import diff_records, diff_files, render_diff, DiffEntry
   from tokamunch.mapping import MappingRecord

   records_a = [MappingRecord(ids_path="a/b", value=1.0)]
   records_b = [MappingRecord(ids_path="a/b", value=2.0)]

   entries: list[DiffEntry] = diff_records(records_a, records_b)
   print(render_diff(entries, "before", "after"))

   # Compare files directly (JSON or IMAS).
   entries = diff_files("baseline.json", "updated.json", ids_names=["magnetics"])
