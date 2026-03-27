Format conversion
=================

tokamunch can move data between three representations:

- **munchi JSON** — the flat ``{concrete_path: value}`` format produced by ``munchi map --output results.json``
- **imas-python files** — HDF5 (``.h5``) and NetCDF (``.nc``) written and read via imas-python
- **imas IDS objects** — live Python objects from ``imas.IDSFactory`` that can be inspected, augmented, and validated before writing

CLI usage
---------

Use ``munchi convert`` to convert between files directly:

.. code-block:: console

   # JSON → IMAS NetCDF
   munchi convert --input results.json --output output.nc

   # JSON → IMAS HDF5 (binary-encoded arrays in the JSON)
   munchi convert --input results.json --output output.h5 --binary-arrays

   # IMAS file → JSON (must name the IDS objects to read)
   munchi convert --input output.nc --output results.json --ids magnetics equilibrium

   # Keep going if one IDS fails validation; write failed records to a companion file
   munchi convert --input results.json --output output.nc --on-imas-error fallback-json

If ``--on-imas-error fallback-json`` is active (the default) and an IDS write
fails, the failed IDS records are saved to ``<output>_fallback.json`` and a
message is printed to stderr.

Library usage
-------------

Reading JSON into IDS objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The primary use case is loading a non-compliant JSON mapping result into
in-memory IDS objects, adding missing required fields, and then writing a
valid IMAS file:

.. code-block:: python

   from pathlib import Path
   import imas
   from tokamunch import read_json_records, records_to_ids_objects

   records = read_json_records(Path("results.json"))
   ids_objects = records_to_ids_objects(records)

   # Augment the IDS with missing required fields before writing
   eq = ids_objects["equilibrium"]
   eq.time_slice[0].time = 0.5
   eq.time_slice[0].global_quantities.ip = 1e6

   with imas.DBEntry("imas:hdf5?path=output", "w") as db:
       for ids_obj in ids_objects.values():
           db.put(ids_obj)

Binary-encoded arrays in JSON
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Large float arrays can be stored compactly as base64 binary blobs.  Pass
``binary_arrays=True`` to any JSON-writing call, or use ``--binary-arrays``
on the CLI.  ``read_json_records`` decodes them back to numpy arrays
automatically:

.. code-block:: python

   from tokamunch.outputs import build_json_results, write_json_file

   write_json_file(
       Path("results.json"),
       build_json_results(records, binary_arrays=True),
       force=True,
   )

   # Later — arrays are decoded back to numpy ndarrays transparently
   records = read_json_records(Path("results.json"))

Reading from IMAS files
~~~~~~~~~~~~~~~~~~~~~~~

Use :func:`~tokamunch.read_imas_records` to extract all non-empty leaf values
from an existing IMAS file.  The IDS names must be supplied because the file
format does not expose its contents without reading each IDS explicitly:

.. code-block:: python

   from pathlib import Path
   from tokamunch import read_imas_records

   records = read_imas_records(Path("output.nc"), ids_names=["magnetics", "equilibrium"])

Handling write errors
~~~~~~~~~~~~~~~~~~~~~

imas-python validates IDS objects when ``dbentry.put()`` is called.  If an IDS
is missing essential fields the call raises an exception.
:func:`~tokamunch.write_ids.write_imas_output` (and ``munchi convert``) catch
failures per-IDS so that other IDS objects are still written.  The function
returns a list of :class:`~tokamunch.write_ids.IdsWriteError` objects:

.. code-block:: python

   from pathlib import Path
   from tokamunch.write_ids import write_imas_output

   errors = write_imas_output(Path("output.nc"), records=records, force=True)
   for err in errors:
       print(f"Failed to write {err.ids_name}: {err.cause}")
       # err.records contains the MappingRecord list for the failed IDS

Set the ``IMAS_AL_DISABLE_VALIDATE=1`` environment variable to skip imas-python
validation if needed during development.

Output options
~~~~~~~~~~~~~~

Both ``munchi map`` and ``munchi convert`` accept these output-related options,
which can also be set in ``munchi.toml`` under ``[run]``:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - CLI flag
     - Config key
     - Description
   * - ``--binary-arrays``
     - ``binary_arrays = true``
     - Encode numpy arrays as base64 binary in JSON output (default: ``false``)
   * - ``--on-imas-error``
     - ``on_imas_error = "..."``
     - ``fallback-json`` (default) or ``raise`` — action on IDS write failure
