API Reference
=============

Library entry points for programmatic use of tokamunch.

.. contents:: Sections
   :local:
   :depth: 1

Context
-------

.. autoclass:: tokamunch.MappingContext
   :members:
   :undoc-members:

Selection
---------

.. autoclass:: tokamunch.IdsSelection
   :members:

.. autoclass:: tokamunch.SinglePathSelection
   :members:

.. autofunction:: tokamunch.selection.generate_selected_paths

IDS schema helpers
------------------

.. autoclass:: tokamunch.IDSHelper
   :members:

.. autofunction:: tokamunch.generate_ids_paths

Mapper interface
----------------

.. autoclass:: tokamunch.TokamapInterface
   :members:

.. autoclass:: tokamunch.MapperProtocol
   :members:

.. autoclass:: tokamunch.DataSource
   :members:

.. autoclass:: tokamunch.DataSourceFactory
   :members:

Configuration
-------------

.. autoclass:: tokamunch.CLIConfig
   :members:

.. autoclass:: tokamunch.MapperConfig
   :members:

.. autoclass:: tokamunch.RunConfig
   :members:

.. autoclass:: tokamunch.ConcurrencyConfig
   :members:

.. autoclass:: tokamunch.DataSourceConfig
   :members:

.. autofunction:: tokamunch.load_cli_config

.. autofunction:: tokamunch.config.apply_config_overrides

Path utilities
--------------

.. autofunction:: tokamunch.concrete_path_to_schema_path
.. autofunction:: tokamunch.concrete_path_to_template
.. autofunction:: tokamunch.parse_concrete_path
.. autofunction:: tokamunch.parse_schema_path
.. autofunction:: tokamunch.render_concrete_path
.. autofunction:: tokamunch.render_schema_path
.. autofunction:: tokamunch.render_array_length_query_path
.. autofunction:: tokamunch.normalise_schema_segment

Mapping execution
-----------------

.. autofunction:: tokamunch.mapping.collect_mapped_values
.. autofunction:: tokamunch.mapping.map_path

.. autoclass:: tokamunch.mapping.MappingRecord
   :members:

.. autoclass:: tokamunch.mapping.MappingSummary
   :members:

IDS writers
-----------

.. autofunction:: tokamunch.set_ids_value
.. autofunction:: tokamunch.resize_and_set_ids_value
.. autofunction:: tokamunch.ensure_ids_arrays_resized
.. autofunction:: tokamunch.resolve_ids_parent
.. autofunction:: tokamunch.resolve_ids_segments

.. autoclass:: tokamunch.write_ids.IdsWriteError
   :members:

Format conversion
-----------------

Functions for moving data between munchi JSON output, imas-python IMAS files
(``.h5``, ``.nc``), and in-memory imas IDS objects.

.. autofunction:: tokamunch.read_json_records
.. autofunction:: tokamunch.records_to_ids_objects
.. autofunction:: tokamunch.read_ids_records
.. autofunction:: tokamunch.read_imas_records
.. autofunction:: tokamunch.convert_file

Diff and comparison
-------------------

.. autofunction:: tokamunch.diff.diff_records
.. autofunction:: tokamunch.diff.diff_files
.. autofunction:: tokamunch.diff.render_diff

.. autoclass:: tokamunch.diff.DiffEntry
   :members:

Checkpointing
-------------

.. autoclass:: tokamunch.checkpoint.Checkpoint
   :members:

.. autofunction:: tokamunch.checkpoint.save_checkpoint
.. autofunction:: tokamunch.checkpoint.load_checkpoint
.. autofunction:: tokamunch.checkpoint.apply_checkpoint

Shell completions
-----------------

.. autofunction:: tokamunch.completions.generate_bash_completion
.. autofunction:: tokamunch.completions.generate_zsh_completion
.. autofunction:: tokamunch.completions.generate_fish_completion
.. autofunction:: tokamunch.completions.get_ids_names

Mapping annotations
-------------------

.. autofunction:: tokamunch.templates.is_comment_stub
.. autofunction:: tokamunch.templates.merge_mapping_stubs
.. autofunction:: tokamunch.templates.build_blank_mapping_template

Profiling
---------

.. autoclass:: tokamunch.profiling.ProfileData
   :members:

.. autoclass:: tokamunch.profiling.PhaseTimings
   :members:

.. autoclass:: tokamunch.profiling.CallStats
   :members:

.. autofunction:: tokamunch.profiling.render_profile_report

Trie
----

.. autofunction:: tokamunch.build_ids_path_trie
.. autofunction:: tokamunch.generate_schema_paths_from_trie
.. autofunction:: tokamunch.expand_ids_path_trie
.. autofunction:: tokamunch.expand_ids_path_trie_segments
