import pytest

from backend.app.workers.retention import purge_old_events


def test_retention_rejects_unsafe_windows() -> None:
    with pytest.raises(ValueError):
        purge_old_events.run(0)
    with pytest.raises(ValueError):
        purge_old_events.run(366)
