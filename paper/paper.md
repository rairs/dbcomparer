---
title: 'dbcomparer: engine-agnostic schema and data comparison for relational databases'
tags:
  - Python
  - databases
  - reproducibility
  - data validation
  - SQL
authors:
  - name: Rakesh  # TODO: full name
    orcid: 0000-0000-0000-0000  # TODO: your ORCID
    affiliation: 1
affiliations:
  - name: TODO Institution, Country
    index: 1
date: 14 November 2026
bibliography: paper.bib
---

# Summary

Relational databases hold much of the data behind scientific and engineering
work: observation catalogues, laboratory information systems, survey
responses and the outputs of simulation pipelines. Researchers often need to
show that two databases hold the same thing. Typical cases are a database
before and after a schema migration, an ETL pipeline re-run on new software
versions, a production system and the archived snapshot deposited with a
paper, or two collaborators' copies of a shared dataset. `dbcomparer` is a
Python package and command-line tool that answers this question for any pair
of databases supported by SQLAlchemy [@sqlalchemy], including databases on
*different* engines (for example PostgreSQL and SQLite). It reports
differences in structure (tables, columns, types, nullability, primary keys,
indexes, foreign keys) and in content (rows added, removed or changed, with
per-column before and after values) as text, Markdown, JSON or HTML. Its exit
codes make it usable as a reproducibility check in continuous integration.

# Statement of need

Reproducibility guidelines ask researchers to verify that derived datasets
are stable across software and infrastructure changes [@wilkinson2016fair;
@sandve2013ten]. For flat files this is easy with checksums or `diff`, but a
database cannot be meaningfully checksummed. Physical row order, storage
format and type spelling differ between engines and even between versions of
one engine, so byte-level comparison flags changes that do not matter and
says nothing about the changes that do.

Existing tools mostly cover a single engine or a single concern.
Migration tools such as Alembic [@alembic] and `migra` [@migra] generate
schema change scripts but do not compare data. Vendor utilities and
PostgreSQL's `pg_dump` are tied to one engine. `data-diff` [@datadiff]
compared data across engines at warehouse scale, but its open-source
development has been archived and it does not report schema differences
together with row-level changes. `dbcomparer` fills the gap with a small,
dependency-light, engine-agnostic tool. It (i) compares schema and data in
one pass, (ii) normalises types and values across drivers so that a
cross-engine comparison is not drowned in spurious differences, (iii)
handles tables without primary keys by multiset comparison, and (iv)
returns machine-readable results that can be checked into a research record
or asserted on in a test suite.

# Design

`dbcomparer` reads schemas with SQLAlchemy's runtime inspection API. Column
types are compared by their generic SQLAlchemy type by default, with an
opt-in strict mode for exact dialect types. Data comparison streams the
source table in chunks into a hash map keyed on the primary key (or
user-specified key columns), then streams the target table and matches each
row against it. This needs one sequential read per table and no
engine-specific ordering or collation behaviour. Values are normalised before
comparison: decimals and floats are unified, booleans are mapped to
integers, binary values are hex-encoded, timezone-aware timestamps are
converted to UTC, and an optional absolute float tolerance is available.
Counts are always exact, and the number of example rows recorded per table
is capped so that reports stay readable.

# Acknowledgements

TODO.

# References
