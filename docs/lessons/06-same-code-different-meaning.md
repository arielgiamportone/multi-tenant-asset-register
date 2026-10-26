# Same account code, different meaning

**Symptom.** While calibrating the yearly revaluation for one tenant, some assets got a
coefficient that made no sense for their class, yet the engine reported no unmapped accounts.

**Cause.** The legacy system and the new chart of accounts were mapped with
`mapping.get(code, code)`: "if there is no explicit mapping, assume the code means the same thing."
For most codes it did. For a few, the **same number named a different asset class** in each chart:
machinery in one, historical heritage in the other. Those assets silently received the wrong
coefficient. Heritage is not even supposed to be revalued.

**Fix.** The mapping is explicit and complete per tenant. Every legacy code is listed, codes that
must not be revalued map to an explicit "blocked" value, and an unknown code is an error. There
is no fallback.

**Takeaway.** An identity fallback in a mapping table is a silent assumption. When two
classification systems share a number space, it is a bug waiting for the right code.
