# quantshark_shared.testing

Reusable test helpers for integration tests with TimescaleDB.

## Minimal setup

```python
# tests/conftest.py
from quantshark_shared.testing.fixtures import *
```

## Optional overrides

- `db_image`
- `db_engine_kwargs`
- `db_session_kwargs`
- `db_truncate_exclude`
