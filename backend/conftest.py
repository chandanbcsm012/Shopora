# Root conftest so the `db_session`/`client` fixtures defined in
# tests/conftest.py are discoverable from every test directory under
# backend/ (including app/modules/*/tests/), not just tests/ itself —
# pytest only auto-loads a conftest.py for directories at or below where
# it lives, and app/modules/*/tests/ is a sibling of tests/, not a
# descendant.
from tests.conftest import client, db_session  # noqa: F401
