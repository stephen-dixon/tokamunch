Profiling and performance
=========================

tokamunch has built-in profiling support to help identify bottlenecks in a
mapping run.  Three complementary tools are available:

- **``--profile-stats``** — a phase-level and per-call report printed to
  ``stderr`` after the run.
- **``--profile FILE``** — a ``cProfile`` stats dump for detailed line-level
  inspection.
- **``--dry-run``** — expand paths without calling the mapper to measure
  expansion overhead in isolation.
- **``--limit N``** — cap the number of paths that are mapped, for quick
  experiments.

.. contents:: Sections
   :local:
   :depth: 1

Phase timing report (``--profile-stats``)
------------------------------------------

Pass ``--profile-stats`` to ``munchi map`` to print a breakdown after the run:

.. code-block:: console

   munchi map --ids magnetics --profile-stats

Example output::

   ── Profiling report ──────────────────────────────────────────
   Phase breakdown:
     [###.................] 14.7%  0.147s  path expansion (incl. array-length queries)
     [####################] 84.2%  0.842s  mapping (mapper.map calls)
     [....................] 0.2%   0.002s  output / file write
     [....................] 0.9%   0.009s  overhead / other
     total: 1.000s

   Call statistics:
     mapper.map()       calls=    142  total=0.842s  mean=5.9ms  min=1.1ms  max=48.2ms
     get_array_length() calls=     18  total=0.147s  mean=8.2ms  min=2.0ms  max=21.5ms

   Bottleneck hints:
     mapper.map() mean=5.9ms — moderate latency. Consider --concurrency-mode thread or process.
   ──────────────────────────────────────────────────────────────

The report shows:

- **Phase breakdown** — wall time in each stage: path expansion (which includes
  all ``get_array_length`` calls to discover array sizes), mapping (the actual
  ``mapper.map()`` calls), and output.
- **Call statistics** — count, total, mean, min, max for each class of external
  call.  ``mapper.map()`` counts *all* calls (including those issued internally
  by ``get_array_length``).
- **Bottleneck hints** — automated interpretation to guide the next tuning step.

Detailed cProfile output (``--profile FILE``)
---------------------------------------------

For line-level detail, write a ``cProfile`` stats file:

.. code-block:: console

   munchi map --ids magnetics --profile mapping.prof

Inspect with the standard library:

.. code-block:: console

   python -m pstats mapping.prof
   # inside pstats:
   sort cumulative
   stats 20

Or with `snakeviz <https://jiffyclub.github.io/snakeviz/>`_ for an
interactive flame graph:

.. code-block:: console

   pip install snakeviz
   snakeviz mapping.prof

The two flags can be combined:

.. code-block:: console

   munchi map --ids magnetics --profile-stats --profile mapping.prof

Isolating path expansion (``--dry-run``)
-----------------------------------------

``--dry-run`` expands all concrete paths (including array-length queries to the
mapper) but skips the actual ``mapper.map()`` data calls.  This lets you
measure expansion overhead in isolation and see the total path count before
committing to a full run:

.. code-block:: console

   munchi map --ids magnetics --dry-run
   # Dry run: 1342 paths expanded in 0.65s (no mapper calls made).

Limiting the number of paths (``--limit N``)
---------------------------------------------

``--limit N`` maps only the first *N* paths (after expansion and any
``--match`` or ``--mapping`` filtering).  Useful for quick sanity-checks and
for estimating per-path throughput:

.. code-block:: console

   munchi map --ids magnetics --limit 20 --profile-stats

Understanding bottlenecks
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - Observation
     - Likely cause
     - Suggested action
   * - Expansion >> mapping time
     - Many array-length queries; deeply nested IDS with many AoS levels
     - ``--leaves-only`` or ``--mapping`` to reduce paths
   * - ``mapper.map()`` mean > 100 ms
     - Network / remote file I/O in data source plugin (latency-bound)
     - ``--concurrency-mode thread`` or ``process``
   * - ``mapper.map()`` mean < 5 ms
     - Local computation (CPU-bound)
     - Threading unlikely to help; profile the plugin itself
   * - Many ``get_array_length`` calls
     - Lots of AoS nodes; slow per-call (same as ``mapper.map()``)
     - Cache array lengths in plugin; or reduce path depth

Library usage
-------------

``ProfileData`` can be used programmatically by passing it to
:func:`~tokamunch.mapping.collect_mapped_values`:

.. code-block:: python

   from tokamunch.profiling import ProfileData, render_profile_report
   from tokamunch.mapping import collect_mapped_values

   profile = ProfileData()
   records, summary = collect_mapped_values(
       ctx, selection, verbose_errors=False, profile=profile
   )
   print(render_profile_report(profile, total_elapsed_s=summary.elapsed_s))

.. autoclass:: tokamunch.profiling.ProfileData
   :members:

.. autoclass:: tokamunch.profiling.PhaseTimings
   :members:

.. autoclass:: tokamunch.profiling.CallStats
   :members:

.. autofunction:: tokamunch.profiling.render_profile_report
