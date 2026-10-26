# Bulk load with explicit ids, then every INSERT failed

**Symptom.** Tenants copied from the file-based store to PostgreSQL were readable, but the first
attempt to create a record returned HTTP 500 (`duplicate key value violates unique constraint`).

**Cause.** The load kept the original ids so that foreign keys stayed valid, which is right.
But an identity column's sequence only advances when PostgreSQL generates the value. After an
explicit-id load every sequence still stood at 1, so the next generated id collided with an
existing row. SQLite's `AUTOINCREMENT` reads the current maximum, so the problem never existed
there.

**Fix.** After any load with explicit ids, for every identity column:

```sql
SELECT setval(pg_get_serial_sequence('assets', 'id'), COALESCE(MAX(id), 0) + 1, false)
FROM assets;
```

That step is part of the loader, and a separate repair script handles tenants that were loaded
earlier.

**How it stays fixed.** The reset is a step of the loader itself, so no load can skip it.
