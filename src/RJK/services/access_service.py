"""Folder-creation access control.

When auth_enabled=False (default for local dev) every check passes immediately.
When auth_enabled=True (deployed server) the service enforces folder rules stored
in data/acl.json.  Users are identified by:
  1. X-Remote-User / Remote-User / X-Forwarded-User request headers (reverse proxy / SSO)
  2. Fallback: os.getlogin() / getpass.getuser() (same process owner as the server)

Folder rules are matched with fnmatch patterns (e.g. "*", "demo/*", "finance/uk/*").
Access is granted when the user belongs to an allowed Unix group OR appears in
the rule's temp_users list with a non-expired entry.
"""
import fnmatch
import getpass
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

try:
    import grp as _grp
    import pwd as _pwd
    _UNIX = True
except ImportError:
    _UNIX = False          # Windows dev environment


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TempUser:
    username: str
    note: str = ""
    added: str = field(default_factory=lambda: date.today().isoformat())
    expires: Optional[str] = None   # ISO date or None = never expires


@dataclass
class FolderRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    folder_pattern: str = "*"
    description: str = ""
    unix_groups: list[str] = field(default_factory=list)
    temp_users: list[TempUser] = field(default_factory=list)


@dataclass
class AclConfig:
    folder_rules: list[FolderRule] = field(default_factory=list)
    admin_groups: list[str] = field(default_factory=list)
    admin_temp_users: list[TempUser] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AccessService:
    def __init__(self, acl_path: Path, auth_enabled: bool = False) -> None:
        self.acl_path = acl_path
        self.auth_enabled = auth_enabled

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def load_config(self) -> AclConfig:
        if not self.acl_path.exists():
            return AclConfig()
        try:
            raw = json.loads(self.acl_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AclConfig()
        rules = [
            FolderRule(
                id=r.get("id", str(uuid.uuid4())[:8]),
                folder_pattern=r.get("folder_pattern", "*"),
                description=r.get("description", ""),
                unix_groups=r.get("unix_groups", []),
                temp_users=[TempUser(**u) for u in r.get("temp_users", [])],
            )
            for r in raw.get("folder_rules", [])
        ]
        return AclConfig(
            folder_rules=rules,
            admin_groups=raw.get("admin_groups", []),
            admin_temp_users=[TempUser(**u) for u in raw.get("admin_temp_users", [])],
        )

    def save_config(self, cfg: AclConfig) -> None:
        self.acl_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "folder_rules": [
                {
                    "id": r.id,
                    "folder_pattern": r.folder_pattern,
                    "description": r.description,
                    "unix_groups": r.unix_groups,
                    "temp_users": [asdict(u) for u in r.temp_users],
                }
                for r in cfg.folder_rules
            ],
            "admin_groups": cfg.admin_groups,
            "admin_temp_users": [asdict(u) for u in cfg.admin_temp_users],
        }
        self.acl_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def config_to_dict(self, cfg: AclConfig) -> dict:
        return {
            "folder_rules": [
                {
                    "id": r.id,
                    "folder_pattern": r.folder_pattern,
                    "description": r.description,
                    "unix_groups": r.unix_groups,
                    "temp_users": [asdict(u) for u in r.temp_users],
                }
                for r in cfg.folder_rules
            ],
            "admin_groups": cfg.admin_groups,
            "admin_temp_users": [asdict(u) for u in cfg.admin_temp_users],
        }

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    def get_current_user(self, headers: dict | None = None) -> str:
        return self.get_current_user_with_source(headers)[0]

    def get_current_user_with_source(self, headers: dict | None = None) -> tuple[str, str]:
        """Return (username, source) where source is 'header' | 'os'."""
        if headers:
            for key in ("x-remote-user", "remote-user", "x-forwarded-user"):
                v = headers.get(key) or headers.get(key.title())
                if v and v.strip():
                    return v.strip().lower(), "header"
        try:
            return getpass.getuser().lower(), "os"
        except Exception:
            return "unknown", "os"

    def get_unix_groups(self, username: str) -> list[str]:
        if not _UNIX:
            return []
        try:
            pw = _pwd.getpwnam(username)
            gids = _get_grouplist(username, pw.pw_gid)
            return [_grp.getgrgid(gid).gr_name for gid in gids]
        except (KeyError, AttributeError):
            pass
        try:
            return [g.gr_name for g in _grp.getgrall() if username in g.gr_mem]
        except Exception:
            return []

    def list_system_groups(self) -> list[dict]:
        """All Unix groups on the server (Linux only)."""
        if not _UNIX:
            return []
        try:
            return sorted(
                [{"name": g.gr_name, "gid": g.gr_gid, "members": list(g.gr_mem)}
                 for g in _grp.getgrall()],
                key=lambda g: g["name"],
            )
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Access checks
    # ------------------------------------------------------------------

    def _temp_active(self, tu: TempUser) -> bool:
        if not tu.expires:
            return True
        try:
            return date.today() <= date.fromisoformat(tu.expires)
        except ValueError:
            return True

    def _user_matches_rule(self, username: str, user_groups: list[str], rule: FolderRule) -> bool:
        if any(g in user_groups for g in rule.unix_groups):
            return True
        return any(
            tu.username.lower() == username and self._temp_active(tu)
            for tu in rule.temp_users
        )

    def is_admin(self, username: str, user_groups: list[str] | None = None,
                 cfg: AclConfig | None = None) -> bool:
        if not self.auth_enabled:
            return True
        cfg = cfg or self.load_config()
        ug = user_groups if user_groups is not None else self.get_unix_groups(username)
        if any(g in ug for g in cfg.admin_groups):
            return True
        return any(
            tu.username.lower() == username and self._temp_active(tu)
            for tu in cfg.admin_temp_users
        )

    def can_create_folder(self, username: str, folder_path: str,
                          headers: dict | None = None) -> tuple[bool, str]:
        """Returns (allowed, reason). Always True when auth is disabled."""
        if not self.auth_enabled:
            return True, "access controls disabled (local run)"

        user_groups = self.get_unix_groups(username)
        cfg = self.load_config()

        if self.is_admin(username, user_groups=user_groups, cfg=cfg):
            return True, "user is admin"

        # Most-specific pattern first (longer pattern = more specific)
        matching = sorted(
            [r for r in cfg.folder_rules
             if fnmatch.fnmatch(folder_path.lower(), r.folder_pattern.lower())],
            key=lambda r: len(r.folder_pattern),
            reverse=True,
        )
        if not matching:
            return False, f"no access rule matches folder '{folder_path}'"

        for rule in matching:
            if self._user_matches_rule(username, user_groups, rule):
                return True, f"matched rule '{rule.folder_pattern}'"

        return False, (
            f"user '{username}' is not in any permitted group or temp-user list "
            f"for folder '{folder_path}'"
        )


# ---------------------------------------------------------------------------
# Portable os.getgrouplist shim
# ---------------------------------------------------------------------------

def _get_grouplist(username: str, primary_gid: int) -> list[int]:
    """Return all GIDs for a user (Unix only)."""
    try:
        import os
        return list(os.getgrouplist(username, primary_gid))   # CPython 3.3+, POSIX
    except AttributeError:
        # Fallback: scan all groups
        return [primary_gid] + [
            g.gr_gid for g in _grp.getgrall() if username in g.gr_mem
        ]
