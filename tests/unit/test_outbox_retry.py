from backend.app.workers.outbox import retry_delay


def test_retry_delay_is_exponential_and_bounded() -> None:
    assert retry_delay(1, 0) == 2
    assert retry_delay(2, 0) == 4
    assert retry_delay(20, 0.5) <= 300.5
