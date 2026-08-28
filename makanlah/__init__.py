"""Shared library for MakanLah.

ingest/ and api/ both import this and share nothing at runtime: separate
processes, separate hosts, separate failure domains (docs/TRD.md). The schema,
the database layer and the model clients live here so they exist once rather
than twice.
"""

__version__ = '0.1.0'
