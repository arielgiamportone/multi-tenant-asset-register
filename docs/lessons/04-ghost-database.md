# One direct `connect()` opened an empty ghost database

**Symptom.** On the PostgreSQL deployment, background jobs stayed in *pending* forever and a
generated public portal came out empty. There were no errors in the web logs.

**Cause.** A few modules still called `sqlite3.connect(path)` directly instead of going through the
engine-aware connector. On the server, that path did not exist, and SQLite **creates an empty
database file** when asked to open a missing one. The code then reported `no such table` from a
background worker whose output nobody watched, or simply found zero rows.

**Fix.** Every connection goes through two helpers that choose the engine and the tenant schema;
the remaining direct calls were swept out of the codebase.

**What it uncovered.** To be sure nothing else leaked, the test suite gained a switch to run
against PostgreSQL. The first run found five more parity bugs that had passed every unit test:
a missing `cursor.description`, a tenant silently falling back to the `public` schema,
integrity errors caught with the SQLite exception type in a dozen places, a boolean column used as
`0/1`, and a query relying on SQLite's implicit `rowid`.

**Takeaway.** "Runs on both engines" is a claim only a test run on both engines can make.
