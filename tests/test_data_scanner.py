"""Tests for DataScanner, ScanResult, and scanner config persistence."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from RJK.services.data_scanner import (
    RESTRICTED_KEYWORDS,
    PII_COMBINATION_KEYWORDS,
    PII_COMBO_THRESHOLD,
    DataScanner,
    ScanFlag,
    ScanResult,
    get_scanner,
    get_scanner_from_path,
    load_scanner_config,
    save_scanner_config,
)


# ---------------------------------------------------------------------------
# ScanResult properties and summary
# ---------------------------------------------------------------------------

class TestScanResult:

    def test_clean_result_no_flags(self):
        r = ScanResult(clean=True, flags=[])
        assert r.clean is True
        assert r.blocked_columns == []
        assert r.warning_columns == []

    def test_blocked_columns_property(self):
        r = ScanResult(clean=False, flags=[
            ScanFlag("USER_PASSWORD", "matches keyword", "blocked"),
            ScanFlag("EMAIL", "PII", "warning"),
        ])
        assert r.blocked_columns == ["USER_PASSWORD"]

    def test_warning_columns_property(self):
        r = ScanResult(clean=False, flags=[
            ScanFlag("USER_PASSWORD", "matches keyword", "blocked"),
            ScanFlag("EMAIL", "PII", "warning"),
        ])
        assert r.warning_columns == ["EMAIL"]

    def test_summary_clean(self):
        assert ScanResult(clean=True).summary() == "No sensitive data detected."

    def test_summary_blocked_only(self):
        r = ScanResult(clean=False, flags=[
            ScanFlag("PWD", "restricted", "blocked"),
        ])
        assert "Blocked columns" in r.summary()
        assert "PWD" in r.summary()

    def test_summary_warning_only(self):
        r = ScanResult(clean=False, flags=[
            ScanFlag("EMAIL", "PII", "warning"),
        ])
        assert "PII combination" in r.summary()
        assert "EMAIL" in r.summary()

    def test_summary_both_blocked_and_warning(self):
        r = ScanResult(clean=False, flags=[
            ScanFlag("PWD", "restricted", "blocked"),
            ScanFlag("EMAIL", "PII", "warning"),
        ])
        summary = r.summary()
        assert "Blocked columns" in summary
        assert "PII combination" in summary
        assert "  |  " in summary


# ---------------------------------------------------------------------------
# DataScanner.scan_columns — restricted keywords
# ---------------------------------------------------------------------------

class TestScanColumnsRestricted:

    def test_clean_columns_return_clean(self):
        s = DataScanner()
        result = s.scan_columns(["PRODUCT", "REGION", "SALES_DATE", "REVENUE"])
        assert result.clean is True
        assert result.flags == []

    def test_exact_restricted_keyword_blocked(self):
        s = DataScanner()
        result = s.scan_columns(["password"])
        assert not result.clean
        assert "password" in result.blocked_columns

    def test_restricted_keyword_as_substring(self):
        s = DataScanner()
        result = s.scan_columns(["USER_PASSWORD_HASH"])
        assert not result.clean
        assert "USER_PASSWORD_HASH" in result.blocked_columns

    def test_case_insensitive_match(self):
        s = DataScanner()
        result = s.scan_columns(["PASSWORD", "MySecret"])
        blocked = result.blocked_columns
        assert "PASSWORD" in blocked
        assert "MySecret" in blocked

    def test_multiple_restricted_columns(self):
        s = DataScanner()
        result = s.scan_columns(["api_key", "ssn", "cvv"])
        assert len(result.blocked_columns) == 3

    def test_each_default_restricted_keyword_caught(self):
        s = DataScanner()
        for kw in RESTRICTED_KEYWORDS:
            r = s.scan_columns([kw])
            assert kw in r.blocked_columns, f"'{kw}' should be blocked"

    def test_blocked_column_not_also_added_as_warning(self):
        # A column already blocked should not appear in warnings
        s = DataScanner(
            restricted_keywords=["email"],
            pii_combination_keywords=["email", "name", "address"],
            pii_combo_threshold=2,
        )
        result = s.scan_columns(["email", "name", "address"])
        assert "email" in result.blocked_columns
        assert "email" not in result.warning_columns

    def test_only_first_matching_keyword_flags_column(self):
        # Column matching multiple restricted keywords → one flag only
        s = DataScanner(restricted_keywords=["pass", "password"])
        result = s.scan_columns(["password"])
        assert result.blocked_columns.count("password") == 1


# ---------------------------------------------------------------------------
# DataScanner.scan_columns — PII combination
# ---------------------------------------------------------------------------

class TestScanColumnsPii:

    def test_below_threshold_no_warning(self):
        s = DataScanner(pii_combo_threshold=3)
        result = s.scan_columns(["email", "name"])   # 2 < threshold
        assert result.clean is True
        assert result.warning_columns == []

    def test_at_threshold_triggers_warning(self):
        s = DataScanner(pii_combo_threshold=3)
        result = s.scan_columns(["email", "name", "address"])
        assert result.warning_columns != []
        assert result.clean is False      # any flag (even warning) → clean=False

    def test_above_threshold_triggers_warning(self):
        s = DataScanner(pii_combo_threshold=2)
        result = s.scan_columns(["email", "phone", "postcode", "dob"])
        assert len(result.warning_columns) == 4

    def test_warning_sets_clean_false(self):
        s = DataScanner(pii_combo_threshold=2)
        result = s.scan_columns(["email", "name"])
        assert result.clean is False     # any flag sets clean=False
        assert result.blocked_columns == []   # but nothing is blocked

    def test_blocked_plus_pii_makes_not_clean(self):
        s = DataScanner(pii_combo_threshold=2)
        result = s.scan_columns(["password", "email", "name"])
        assert result.clean is False

    def test_custom_pii_keywords_and_threshold(self):
        s = DataScanner(
            pii_combination_keywords=["alpha", "beta", "gamma"],
            pii_combo_threshold=2,
        )
        result = s.scan_columns(["alpha_col", "beta_col"])
        assert len(result.warning_columns) == 2

    def test_empty_columns_list(self):
        s = DataScanner()
        result = s.scan_columns([])
        assert result.clean is True
        assert result.flags == []

    def test_non_pii_columns_ignored(self):
        s = DataScanner()
        result = s.scan_columns(["PRODUCT", "UNITS", "REVENUE", "DATE"])
        assert result.clean is True


# ---------------------------------------------------------------------------
# DataScanner.cleanse
# ---------------------------------------------------------------------------

class TestCleanse:

    def test_removes_specified_columns(self):
        s = DataScanner()
        rows = [{"name": "Alice", "email": "a@b.com", "score": 99}]
        out = s.cleanse(rows, ["email"])
        assert "email" not in out[0]
        assert out[0]["name"] == "Alice"
        assert out[0]["score"] == 99

    def test_removes_multiple_columns(self):
        s = DataScanner()
        rows = [{"a": 1, "b": 2, "c": 3}]
        out = s.cleanse(rows, ["a", "c"])
        assert list(out[0].keys()) == ["b"]

    def test_empty_remove_list_leaves_rows_unchanged(self):
        s = DataScanner()
        rows = [{"x": 1, "y": 2}]
        out = s.cleanse(rows, [])
        assert out == rows

    def test_non_existent_column_ignored(self):
        s = DataScanner()
        rows = [{"a": 1}]
        out = s.cleanse(rows, ["does_not_exist"])
        assert out == rows

    def test_all_rows_cleansed(self):
        s = DataScanner()
        rows = [{"keep": i, "drop": i * 2} for i in range(5)]
        out = s.cleanse(rows, ["drop"])
        assert all("drop" not in r for r in out)
        assert len(out) == 5

    def test_empty_rows_returns_empty(self):
        s = DataScanner()
        assert s.cleanse([], ["email"]) == []

    def test_original_rows_not_mutated(self):
        s = DataScanner()
        rows = [{"a": 1, "b": 2}]
        s.cleanse(rows, ["b"])
        assert "b" in rows[0]   # original unchanged


# ---------------------------------------------------------------------------
# Custom keyword initialisation
# ---------------------------------------------------------------------------

class TestCustomKeywords:

    def test_custom_restricted_replaces_defaults(self):
        s = DataScanner(restricted_keywords=["secret_code"])
        # default keywords should NOT trigger
        result = s.scan_columns(["password"])
        assert result.clean is True
        # custom keyword should trigger
        result2 = s.scan_columns(["secret_code"])
        assert not result2.clean

    def test_custom_pii_replaces_defaults(self):
        s = DataScanner(
            pii_combination_keywords=["foo", "bar", "baz"],
            pii_combo_threshold=2,
        )
        result = s.scan_columns(["foo_col", "bar_col"])
        assert len(result.warning_columns) == 2

    def test_threshold_one_flags_any_pii_column(self):
        s = DataScanner(pii_combination_keywords=["email"], pii_combo_threshold=1)
        result = s.scan_columns(["email"])
        assert "email" in result.warning_columns


# ---------------------------------------------------------------------------
# get_scanner factory
# ---------------------------------------------------------------------------

class TestGetScanner:

    def test_returns_data_scanner_instance(self):
        assert isinstance(get_scanner(), DataScanner)

    def test_uses_default_keywords(self):
        s = get_scanner()
        result = s.scan_columns(["password"])
        assert not result.clean


# ---------------------------------------------------------------------------
# load_scanner_config / save_scanner_config / get_scanner_from_path
# ---------------------------------------------------------------------------

class TestScannerConfig:

    def test_load_returns_defaults_when_no_file(self, tmp_path):
        cfg = load_scanner_config(tmp_path / "missing.json")
        assert cfg["restricted_keywords"] == list(RESTRICTED_KEYWORDS)
        assert cfg["pii_combination_keywords"] == list(PII_COMBINATION_KEYWORDS)
        assert cfg["pii_combo_threshold"] == PII_COMBO_THRESHOLD

    def test_save_then_load_round_trips(self, tmp_path):
        p = tmp_path / "scanner.json"
        original = load_scanner_config(p)
        save_scanner_config(p, original)
        reloaded = load_scanner_config(p)
        assert reloaded == original

    def test_saved_keywords_persist(self, tmp_path):
        p = tmp_path / "scanner.json"
        cfg = {
            "restricted_keywords": ["custom_secret"],
            "pii_combination_keywords": ["foo", "bar"],
            "pii_combo_threshold": 2,
        }
        save_scanner_config(p, cfg)
        loaded = load_scanner_config(p)
        assert loaded["restricted_keywords"] == ["custom_secret"]
        assert loaded["pii_combination_keywords"] == ["foo", "bar"]
        assert loaded["pii_combo_threshold"] == 2

    def test_load_falls_back_to_defaults_on_corrupt_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json", encoding="utf-8")
        cfg = load_scanner_config(p)
        assert cfg["restricted_keywords"] == list(RESTRICTED_KEYWORDS)

    def test_load_uses_module_default_for_missing_keys(self, tmp_path):
        p = tmp_path / "partial.json"
        p.write_text(json.dumps({"restricted_keywords": ["only_this"]}), encoding="utf-8")
        cfg = load_scanner_config(p)
        assert cfg["restricted_keywords"] == ["only_this"]
        assert cfg["pii_combination_keywords"] == list(PII_COMBINATION_KEYWORDS)
        assert cfg["pii_combo_threshold"] == PII_COMBO_THRESHOLD

    def test_save_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "dir" / "scanner.json"
        save_scanner_config(p, {"restricted_keywords": [], "pii_combination_keywords": [], "pii_combo_threshold": 3})
        assert p.exists()

    def test_get_scanner_from_path_no_file_uses_defaults(self, tmp_path):
        s = get_scanner_from_path(tmp_path / "missing.json")
        result = s.scan_columns(["password"])
        assert not result.clean

    def test_get_scanner_from_path_uses_saved_keywords(self, tmp_path):
        p = tmp_path / "scanner.json"
        save_scanner_config(p, {
            "restricted_keywords": ["my_forbidden"],
            "pii_combination_keywords": [],
            "pii_combo_threshold": 3,
        })
        s = get_scanner_from_path(p)
        # custom keyword blocked
        assert not s.scan_columns(["my_forbidden"]).clean
        # default keyword no longer applies
        assert s.scan_columns(["password"]).clean

    def test_get_scanner_from_path_uses_saved_threshold(self, tmp_path):
        p = tmp_path / "scanner.json"
        save_scanner_config(p, {
            "restricted_keywords": [],
            "pii_combination_keywords": ["email", "name"],
            "pii_combo_threshold": 2,
        })
        s = get_scanner_from_path(p)
        result = s.scan_columns(["email", "name"])
        assert len(result.warning_columns) == 2
