# A failed SELECT poisoned the whole PostgreSQL transaction

**Symptom.** After moving to PostgreSQL, the home page of newly created tenants returned HTTP 500.
Older tenants were fine. The stack trace pointed at an unrelated query, far from the real failure.

**Cause.** Some optional tables were created lazily, the first time a feature was used. The
dashboard read them inside `try/except sqlite3.OperationalError` and showed zero on failure.
On PostgreSQL the missing table raises a *different* exception type, so the `except` did not
match. Worse, PostgreSQL marks the transaction as aborted after any error: **every following
statement fails** with `current transaction is aborted` until a rollback. SQLite has no such state,
so the pattern had always "worked".

**Fix.**

```python
except db_errors() as exc:        # both engines' error types, from one helper
    conn.rollback()               # clear the aborted state before the next query
    return 0
```

The structural fix is to create the optional tables when the tenant is provisioned, so the
"table might not exist" branch disappears altogether.

**How it stays fixed.** Eight dashboard KPI tests cover a tenant where the optional tables do not
exist yet.
