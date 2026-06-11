"""Generate Plotly figures from persisted aggregation data."""
import json
import ssl
from pathlib import Path
from typing import Optional
from urllib.request import urlopen

import pandas as pd
import plotly.express as px

# ---------------------------------------------------------------------------
# Region detection constants
# ---------------------------------------------------------------------------

US_STATE_ABBREVS = frozenset([
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
    'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY','DC',
])

UK_COUNTY_SAMPLE = frozenset([
    'greater london','greater manchester','west yorkshire','west midlands',
    'south yorkshire','merseyside','tyne and wear','kent','essex','hampshire',
    'lancashire','hertfordshire','surrey','norfolk','suffolk','derbyshire',
    'nottinghamshire','leicestershire','staffordshire','oxfordshire',
    'gloucestershire','buckinghamshire','berkshire','cambridgeshire',
    'northamptonshire','cumbria','cornwall','devon','somerset','wiltshire',
    'cheshire','lincolnshire','shropshire','worcestershire','herefordshire',
    'northumberland','durham','north yorkshire','east riding of yorkshire',
    'east sussex','west sussex','dorset','rutland',
    'glasgow city','edinburgh','highland','fife','north lanarkshire',
    'south lanarkshire','aberdeenshire','perth and kinross','dundee city',
    'cardiff','swansea','rhondda cynon taf','caerphilly','newport',
])

# UK Local Authority Districts — martinjc/UK-GeoJSON (cached on first use)
_UK_LAD_URL = (
    "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/"
    "master/json/administrative/gb/lad.json"
)
_UK_LAD_FEATURE_KEY = "properties.LAD13NM"

SUPPORTED_CHART_TYPES = [
    'bar', 'bar_h', 'bar_stack', 'pie', 'donut',
    'line', 'scatter', 'heatmap', 'map',
]


# ---------------------------------------------------------------------------
# ChartService
# ---------------------------------------------------------------------------

class ChartService:
    def __init__(self, geojson_cache_dir: Path) -> None:
        self._cache = Path(geojson_cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        rows: list[dict],
        chart_type: str,
        x: str,
        y: str,
        color: Optional[str],
        title: str,
        show_legend: bool = False,
    ) -> dict:
        if chart_type not in SUPPORTED_CHART_TYPES:
            raise ValueError(f"chart_type must be one of {SUPPORTED_CHART_TYPES}")
        if not rows:
            raise ValueError("Dataset is empty")

        df = pd.DataFrame(rows)
        _check_cols(df, x, y, color)

        if chart_type == 'bar':
            fig = px.bar(df, x=x, y=y, color=color, title=title, barmode='group')
        elif chart_type == 'bar_h':
            fig = px.bar(df, x=y, y=x, color=color, title=title, orientation='h', barmode='group')
        elif chart_type == 'bar_stack':
            fig = px.bar(df, x=x, y=y, color=color, title=title, barmode='stack')
        elif chart_type == 'pie':
            fig = px.pie(df, names=x, values=y, title=title)
        elif chart_type == 'donut':
            fig = px.pie(df, names=x, values=y, title=title, hole=0.45)
        elif chart_type == 'line':
            fig = px.line(df, x=x, y=y, color=color, title=title, markers=True)
        elif chart_type == 'scatter':
            fig = px.scatter(df, x=x, y=y, color=color, title=title)
        elif chart_type == 'heatmap':
            if not color:
                raise ValueError("Heatmap requires a Group / Colour column")
            pivot = df.pivot_table(index=x, columns=color, values=y, aggfunc='sum', fill_value=0)
            fig = px.imshow(pivot, title=title, aspect='auto', color_continuous_scale='Blues')
        elif chart_type == 'map':
            fig = self._map(df, x, y, title)

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=40, r=20, t=60, b=40),
            showlegend=show_legend,
        )
        return json.loads(fig.to_json())

    # ------------------------------------------------------------------
    # Map helpers
    # ------------------------------------------------------------------

    def _detect_region_type(self, values: list) -> str:
        sample = {str(v).strip() for v in values if v}
        if not sample:
            return 'world'
        if len({v.upper() for v in sample} & US_STATE_ABBREVS) / len(sample) >= 0.7:
            return 'us_states'
        if len({v.lower() for v in sample} & UK_COUNTY_SAMPLE) / len(sample) >= 0.4:
            return 'uk_counties'
        return 'world'

    def _map(self, df: pd.DataFrame, loc_col: str, val_col: str, title: str):
        rtype = self._detect_region_type(df[loc_col].tolist())
        vmin = float(df[val_col].min())
        vmax = float(df[val_col].max())
        # Ensure min != max so the full colour range is used
        if vmin == vmax:
            vmin = 0.0

        if rtype == 'us_states':
            fig = px.choropleth(
                df, locations=loc_col, locationmode='USA-states',
                color=val_col, title=title, scope='usa',
                color_continuous_scale='YlOrRd',
                range_color=[vmin, vmax],
            )
            fig.update_geos(showland=True, landcolor='#e8e8e8', showocean=True, oceancolor='#cce5f6')
            return fig

        if rtype == 'uk_counties':
            geojson = self._load_uk_geojson()
            if geojson:
                df2 = self._normalize_to_geojson(df, loc_col, geojson, _UK_LAD_FEATURE_KEY)
                fig = px.choropleth(
                    df2, geojson=geojson,
                    locations=loc_col, featureidkey=_UK_LAD_FEATURE_KEY,
                    color=val_col, title=title,
                    color_continuous_scale='YlOrRd',
                    range_color=[vmin, vmax],
                )
                fig.update_geos(fitbounds='locations', visible=False)
                return fig
            return px.bar(df, x=loc_col, y=val_col, title=f"{title} (UK map data unavailable — check network)")

        # World countries
        fig = px.choropleth(
            df, locations=loc_col, locationmode='country names',
            color=val_col, title=title,
            color_continuous_scale='YlOrRd',
            range_color=[vmin, vmax],
        )
        fig.update_geos(
            showland=True, landcolor='#e8e8e8',
            showocean=True, oceancolor='#cce5f6',
            showcoastlines=True, coastlinecolor='#aaaaaa',
            fitbounds='locations',
        )
        return fig

    def _normalize_to_geojson(self, df: pd.DataFrame, col: str, geojson: dict, feature_key: str) -> pd.DataFrame:
        keys = feature_key.split('.')
        names = []
        for feat in geojson.get('features', []):
            v = feat
            for k in keys:
                v = (v or {}).get(k, {})
            if isinstance(v, str):
                names.append(v)
        lookup = {n.lower(): n for n in names}
        df = df.copy()
        df[col] = df[col].apply(lambda v: lookup.get(str(v).strip().lower(), str(v)))
        return df

    def _load_uk_geojson(self) -> dict | None:
        cache = self._cache / 'uk_lad.geojson'
        if cache.exists():
            try:
                return json.loads(cache.read_text(encoding='utf-8'))
            except Exception:
                pass
        try:
            ctx = ssl.create_default_context()
            with urlopen(_UK_LAD_URL, context=ctx, timeout=20) as r:
                raw = r.read().decode('utf-8')
            cache.write_text(raw, encoding='utf-8')
            return json.loads(raw)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_cols(df: pd.DataFrame, x: str, y: str, color: Optional[str]) -> None:
    for col in [x, y]:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in dataset")
    if color and color not in df.columns:
        raise ValueError(f"Group/colour column '{color}' not found in dataset")


def infer_columns(rows: list[dict]) -> list[dict]:
    """Return [{name, type}] with type = 'number' or 'string'."""
    if not rows:
        return []
    df = pd.DataFrame(rows[:50])  # sample
    result = []
    for col in df.columns:
        dtype = 'number' if pd.api.types.is_numeric_dtype(df[col]) else 'string'
        result.append({'name': col, 'type': dtype})
    return result
