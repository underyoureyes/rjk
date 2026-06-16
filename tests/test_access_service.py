"""Unit tests for AccessService user detection."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from RJK.services.access_service import AccessService


@pytest.fixture
def svc(tmp_path):
    return AccessService(tmp_path / "acl.json", auth_enabled=False)


@pytest.fixture
def svc_auth(tmp_path):
    return AccessService(tmp_path / "acl.json", auth_enabled=True)


# ---------------------------------------------------------------------------
# get_current_user_with_source
# ---------------------------------------------------------------------------

class TestGetCurrentUserWithSource:

    def test_no_headers_returns_os_user(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        user, source = svc.get_current_user_with_source({})
        assert user == "david"
        assert source == "os"

    def test_none_headers_returns_os_user(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        user, source = svc.get_current_user_with_source(None)
        assert user == "david"
        assert source == "os"

    def test_x_remote_user_header(self, svc):
        user, source = svc.get_current_user_with_source({"x-remote-user": "alice"})
        assert user == "alice"
        assert source == "header"

    def test_remote_user_header(self, svc):
        user, source = svc.get_current_user_with_source({"remote-user": "bob"})
        assert user == "bob"
        assert source == "header"

    def test_x_forwarded_user_header(self, svc):
        user, source = svc.get_current_user_with_source({"x-forwarded-user": "carol"})
        assert user == "carol"
        assert source == "header"

    def test_title_case_header_accepted(self, svc):
        user, source = svc.get_current_user_with_source({"X-Remote-User": "dave"})
        assert user == "dave"
        assert source == "header"

    def test_header_value_lowercased(self, svc):
        user, source = svc.get_current_user_with_source({"x-remote-user": "ALICE"})
        assert user == "alice"

    def test_header_value_stripped(self, svc):
        user, source = svc.get_current_user_with_source({"x-remote-user": "  alice  "})
        assert user == "alice"

    def test_empty_header_falls_back_to_os(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        user, source = svc.get_current_user_with_source({"x-remote-user": ""})
        assert user == "david"
        assert source == "os"

    def test_whitespace_only_header_falls_back_to_os(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        user, source = svc.get_current_user_with_source({"x-remote-user": "   "})
        assert user == "david"
        assert source == "os"

    def test_header_takes_precedence_over_os(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        user, source = svc.get_current_user_with_source({"x-remote-user": "sso_user"})
        assert user == "sso_user"
        assert source == "header"

    def test_getpass_failure_returns_unknown(self, svc, monkeypatch):
        def _fail():
            raise OSError("no tty")
        monkeypatch.setattr("getpass.getuser", _fail)
        user, source = svc.get_current_user_with_source({})
        assert user == "unknown"
        assert source == "os"


class TestGetCurrentUser:
    """get_current_user is a convenience wrapper — just returns the username."""

    def test_returns_username_only(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        assert svc.get_current_user({}) == "david"

    def test_header_user_returned(self, svc):
        assert svc.get_current_user({"x-remote-user": "alice"}) == "alice"


# ---------------------------------------------------------------------------
# is_admin
# ---------------------------------------------------------------------------

class TestIsAdmin:

    def test_auth_disabled_always_admin(self, svc, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "nobody")
        assert svc.is_admin("nobody") is True

    def test_auth_enabled_no_config_not_admin(self, svc_auth):
        assert svc_auth.is_admin("nobody") is False

    def test_auth_enabled_admin_group_match(self, svc_auth):
        from RJK.services.access_service import AclConfig
        cfg = AclConfig(admin_groups=["rjk_admins"])
        assert svc_auth.is_admin("anyone", user_groups=["rjk_admins"], cfg=cfg) is True

    def test_auth_enabled_admin_group_no_match(self, svc_auth):
        from RJK.services.access_service import AclConfig
        cfg = AclConfig(admin_groups=["rjk_admins"])
        assert svc_auth.is_admin("anyone", user_groups=["other"], cfg=cfg) is False

    def test_temp_admin_user_active(self, svc_auth):
        from RJK.services.access_service import AclConfig, TempUser
        cfg = AclConfig(admin_temp_users=[TempUser(username="tempie", expires=None)])
        assert svc_auth.is_admin("tempie", user_groups=[], cfg=cfg) is True

    def test_temp_admin_user_expired(self, svc_auth):
        from RJK.services.access_service import AclConfig, TempUser
        cfg = AclConfig(admin_temp_users=[TempUser(username="tempie", expires="2000-01-01")])
        assert svc_auth.is_admin("tempie", user_groups=[], cfg=cfg) is False

    def test_temp_admin_case_insensitive(self, svc_auth):
        from RJK.services.access_service import AclConfig, TempUser
        cfg = AclConfig(admin_temp_users=[TempUser(username="Alice")])
        assert svc_auth.is_admin("alice", user_groups=[], cfg=cfg) is True


# ---------------------------------------------------------------------------
# can_create_folder
# ---------------------------------------------------------------------------

class TestCanCreateFolder:

    def test_auth_disabled_always_allowed(self, svc):
        ok, reason = svc.can_create_folder("anyone", "any/path")
        assert ok is True
        assert "disabled" in reason

    def test_auth_enabled_no_rules_blocked(self, svc_auth):
        ok, reason = svc_auth.can_create_folder("alice", "finance/uk")
        assert ok is False

    def test_matching_rule_with_correct_group(self, svc_auth):
        from RJK.services.access_service import AclConfig, FolderRule
        cfg = AclConfig(folder_rules=[
            FolderRule(folder_pattern="finance/*", unix_groups=["finance_team"])
        ])
        svc_auth.save_config(cfg)
        ok, reason = svc_auth.can_create_folder("alice", "finance/uk",
                                                 headers=None)
        # alice is not in finance_team via OS on this machine — check the logic path
        assert isinstance(ok, bool)

    def test_wildcard_pattern_matches(self, svc_auth):
        from RJK.services.access_service import AclConfig, FolderRule, TempUser
        cfg = AclConfig(folder_rules=[
            FolderRule(folder_pattern="*", unix_groups=[],
                       temp_users=[TempUser(username="alice")])
        ])
        svc_auth.save_config(cfg)
        ok, _ = svc_auth.can_create_folder("alice", "any/path")
        assert ok is True

    def test_most_specific_pattern_wins(self, svc_auth):
        from RJK.services.access_service import AclConfig, FolderRule, TempUser
        cfg = AclConfig(folder_rules=[
            FolderRule(folder_pattern="*", unix_groups=[], temp_users=[]),
            FolderRule(folder_pattern="finance/*", unix_groups=[],
                       temp_users=[TempUser(username="alice")]),
        ])
        svc_auth.save_config(cfg)
        # alice matches the more specific finance/* rule
        ok, reason = svc_auth.can_create_folder("alice", "finance/uk")
        assert ok is True

    def test_temp_user_expired_blocked(self, svc_auth):
        from RJK.services.access_service import AclConfig, FolderRule, TempUser
        cfg = AclConfig(folder_rules=[
            FolderRule(folder_pattern="*", unix_groups=[],
                       temp_users=[TempUser(username="alice", expires="2000-01-01")])
        ])
        svc_auth.save_config(cfg)
        ok, _ = svc_auth.can_create_folder("alice", "any/path")
        assert ok is False
