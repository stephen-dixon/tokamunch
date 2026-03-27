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

Path utilities
--------------

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

Trie
----

.. autofunction:: tokamunch.build_ids_path_trie
.. autofunction:: tokamunch.generate_schema_paths_from_trie
.. autofunction:: tokamunch.expand_ids_path_trie
.. autofunction:: tokamunch.expand_ids_path_trie_segments
