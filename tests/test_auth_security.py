from security.authentication import clear_login_failures, login_allowed, record_login_failure


def test_login_throttle_blocks_after_repeated_failures():
    identifier = "throttle-test@example.com"
    clear_login_failures(identifier)
    for _ in range(5):
        assert login_allowed(identifier)
        record_login_failure(identifier)
    assert not login_allowed(identifier)
    clear_login_failures(identifier)