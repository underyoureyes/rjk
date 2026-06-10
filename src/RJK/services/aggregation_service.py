import pandas as pd

from RJK.services.report_service import ReportService

SUPPORTED_FUNCS = frozenset({"sum", "mean", "max", "min"})


class AggregationService:
    def __init__(self, report_service: ReportService) -> None:
        self.report_service = report_service

    def preview(
        self,
        report_path: str,
        params: dict,
        group_by: list[str],
        value_cols: dict[str, str],  # {column: function}
    ) -> dict:
        if not group_by:
            raise ValueError("group_by must contain at least one column")
        if not value_cols:
            raise ValueError("value_cols must contain at least one column")

        bad_funcs = {f for f in value_cols.values() if f not in SUPPORTED_FUNCS}
        if bad_funcs:
            raise ValueError(
                f"Unsupported function(s) {sorted(bad_funcs)}. Choose from: {', '.join(sorted(SUPPORTED_FUNCS))}"
            )

        result = self.report_service.run_report(report_path, params, run_by="aggs-preview", limit=None)
        rows = result["rows"]
        if not rows:
            return {"rows": [], "row_count": 0}

        df = pd.DataFrame(rows)

        missing_grp = [c for c in group_by if c not in df.columns]
        if missing_grp:
            raise ValueError(f"Unknown group-by column(s): {missing_grp}")
        missing_val = [c for c in value_cols if c not in df.columns]
        if missing_val:
            raise ValueError(f"Unknown value column(s): {missing_val}")

        agg_df = df.groupby(group_by, as_index=False).agg(value_cols)
        for col in value_cols:
            if pd.api.types.is_float_dtype(agg_df[col]):
                agg_df[col] = agg_df[col].round(6)

        # Lowercase all output columns; value cols get a _func suffix
        rename = {col: f"{col}_{func}".lower() for col, func in value_cols.items()}
        rename.update({col: col.lower() for col in group_by})
        agg_df = agg_df.rename(columns=rename)

        return {"rows": agg_df.to_dict(orient="records"), "row_count": len(agg_df)}
