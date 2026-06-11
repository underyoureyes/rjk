"""Scan dataset columns for sensitive/restricted data patterns."""
import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Configurable keyword lists — edit freely
# ---------------------------------------------------------------------------

# Individual column name keywords that are always flagged
RESTRICTED_KEYWORDS: list[str] = [
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "private_key", "passphrase", "credential",
    "ssn", "social_security", "national_id", "passport",
    "credit_card", "card_number", "cvv", "pan",
]

# Column name keywords that form PII when found in combination
PII_COMBINATION_KEYWORDS: list[str] = [
    "name", "first_name", "last_name", "surname", "forename",
    "address", "street", "postcode", "zip", "city",
    "phone", "mobile", "telephone", "fax",
    "email", "dob", "date_of_birth", "birth_date",
    "gender", "ethnicity", "nationality",
    "salary", "income", "bank_account", "iban", "sort_code",
    "ip_address", "mac_address",
]

# Minimum number of PII-combination columns to trigger a PII flag
PII_COMBO_THRESHOLD: int = 3


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ScanFlag:
    column: str
    reason: str
    severity: str  # "blocked" | "warning"


@dataclass
class ScanResult:
    clean: bool                       # False if any "blocked" flags
    flags: list[ScanFlag] = field(default_factory=list)

    @property
    def blocked_columns(self) -> list[str]:
        return [f.column for f in self.flags if f.severity == "blocked"]

    @property
    def warning_columns(self) -> list[str]:
        return [f.column for f in self.flags if f.severity == "warning"]

    def summary(self) -> str:
        if self.clean:
            return "No sensitive data detected."
        parts = []
        if self.blocked_columns:
            parts.append(f"Blocked columns: {', '.join(self.blocked_columns)}")
        if self.warning_columns:
            parts.append(f"PII combination: {', '.join(self.warning_columns)}")
        return "  |  ".join(parts)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class DataScanner:
    def __init__(
        self,
        restricted_keywords: Optional[list[str]] = None,
        pii_combination_keywords: Optional[list[str]] = None,
        pii_combo_threshold: int = PII_COMBO_THRESHOLD,
    ) -> None:
        self._restricted  = [k.lower() for k in (restricted_keywords or RESTRICTED_KEYWORDS)]
        self._pii_combo   = [k.lower() for k in (pii_combination_keywords or PII_COMBINATION_KEYWORDS)]
        self._threshold   = pii_combo_threshold

    def scan_columns(self, columns: list[str]) -> ScanResult:
        flags: list[ScanFlag] = []
        norm = [c.lower() for c in columns]

        # Check each column against restricted keywords
        for col, col_norm in zip(columns, norm):
            for kw in self._restricted:
                if kw in col_norm:
                    flags.append(ScanFlag(column=col, reason=f"matches restricted keyword '{kw}'", severity="blocked"))
                    break

        # Check for PII combination
        pii_hits = [col for col, col_norm in zip(columns, norm)
                    if any(kw in col_norm for kw in self._pii_combo)]
        if len(pii_hits) >= self._threshold:
            for col in pii_hits:
                if not any(f.column == col for f in flags):
                    flags.append(ScanFlag(column=col, reason="part of PII combination", severity="warning"))

        return ScanResult(clean=not any(f.severity == "blocked" for f in flags) and len(flags) == 0, flags=flags)

    def cleanse(self, rows: list[dict], columns_to_remove: list[str]) -> list[dict]:
        """Return rows with the specified columns removed."""
        remove_set = set(columns_to_remove)
        return [{k: v for k, v in row.items() if k not in remove_set} for row in rows]


def get_scanner() -> DataScanner:
    return DataScanner()
