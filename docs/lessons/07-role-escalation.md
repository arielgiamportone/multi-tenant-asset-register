# The role check allowed promoting yourself

**Symptom.** None in production. It was found by a self-run review against the OWASP Top 10.

**Cause.** The user-management endpoint checked that the requested role was *valid*, by
membership in the list of all roles. That list included the vendor's super-administrator role,
so a tenant administrator could create or edit a user with more privileges than their own.

**Fix.** A dedicated guard decides what a caller may **grant**, not just what exists. The vendor
role can never be assigned from inside a tenant.

**How it stays fixed.** Seven regression tests cover the escalation paths. The rest of the
review became a prioritised remediation plan.

**Takeaway.** "Is this a valid value?" and "may this caller set this value?" are different
questions. Validation answers the first, authorisation the second.
