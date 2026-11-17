"""
Settings every test starts with.

RULES_BOT=stub overrides any RULES_BOT=real in your .env (environment variables win over .env), so starting the app
in a test never loads the real bot, and no test can call the paid API (record 0035).
"""

import pytest


# Every test runs with the stub bot, whatever .env says
@pytest.fixture(autouse=True)
def stub_rules_bot_setting(monkeypatch):
    monkeypatch.setenv("RULES_BOT", "stub")
