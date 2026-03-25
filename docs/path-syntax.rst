Path syntax
===========

Concrete runtime path
---------------------

.. code-block:: text

   magnetics/flux_loop[0]/position[0]/r

Non-concrete IDS/schema path
----------------------------

.. code-block:: text

   magnetics/flux_loop(:)/position(:)/r

Mapping-template path
---------------------

.. code-block:: text

   magnetics/flux_loop[#]/position[#]/r

Array-struct node markers ending in ``/#`` are collapsed in mapping templates:

.. code-block:: text

   magnetics/flux_loop(:)/position/#  ->  magnetics/flux_loop[#]/position
