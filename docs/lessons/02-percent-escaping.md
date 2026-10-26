# Escape `%` only when parameters are passed

**Problem.** Translating placeholders (`?` → `%s`) looks like a one-line `replace`. It is not.

**Cause.** The PostgreSQL driver uses `%`-formatting to bind parameters. A statement like
`... WHERE name LIKE '%park%' AND id = ?` contains three `%` signs, and the driver tried to bind
all of them, so the statement fails. The obvious fix, always doubling every `%`, breaks the
opposite case. When **no** parameters are passed, the driver does not format at all, so
`'%%park%%'` would reach the server literally and match nothing.

**Fix.** The translator takes `has_params` and escapes `%` then and only then, in code and in
string literals alike, while `?` is only replaced outside literals:

```python
to_postgres("SELECT * FROM t WHERE n LIKE '%park%' AND id = ?", has_params=True)
# SELECT * FROM t WHERE n LIKE '%%park%%' AND id = %s
to_postgres("SELECT * FROM t WHERE n LIKE '%park%'", has_params=False)
# unchanged
```

**How it stays fixed.** Both cases are tests in the [demo](../../tests/test_sql_dialect.py), and a
mutation that always escapes makes one of them fail.
