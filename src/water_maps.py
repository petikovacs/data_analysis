"""
Geospatial Mapping Utilities (Plotly choropleths)
=================================================
Reusable world-map builders for the water stress project. Used by
`notebooks/02_eda_and_maps.ipynb` and intended for reuse in the dashboard.

Every function returns a `plotly.graph_objects.Figure`; countries are matched on
the ISO 3166-1 alpha-3 code (`ISO3_Code`) produced by the cleaning pipeline.
Figures can be shown interactively (`fig.show()`), saved as interactive HTML
(`fig.write_html(...)`) or exported as static PNG (`fig.write_image(...)`, needs kaleido).
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# One colour per UN SDG 6.4.2 tier, shared by every chart in the project
TIER_COLORS = {
    '1. No Stress (<25%)': '#2c7bb6',
    '2. Low Stress (25-50%)': '#abd9e9',
    '3. Medium Stress (50-75%)': '#fee090',
    '4. High Stress (75-100%)': '#fdae61',
    '5. Critical Stress (>100%)': '#d7191c',
    'Unknown': '#e0e0e0',
}
TIER_ORDER = list(TIER_COLORS)

_GEO = dict(showframe=False, showcoastlines=False, projection_type='natural earth',
            projection_rotation=dict(lon=10), lataxis_range=[-57, 84],  # Europe/Africa centred, no Antarctica
            showland=True, landcolor='#f2f2f2', showcountries=True, countrycolor='white')


def _layout(fig, title, legend_title=None):
    """Apply the shared map layout (projection, margins, fonts)."""
    fig.update_geos(**_GEO)
    fig.update_layout(title=dict(text=title, x=0.01, font=dict(size=16)),
                      margin=dict(l=0, r=0, t=50, b=0), font=dict(family='Arial', size=12),
                      legend_title_text=legend_title, paper_bgcolor='white')
    return fig


def stress_tier_map(df, year=None, title=None):
    """Categorical map of UN water stress tiers.

    Args:
        df: master dataset (needs ISO3_Code, Country, Year, Water_Stress_Total_Pct,
            Water_Stress_Category). If `year` is None, each country's latest
            available value is used.
        year: calendar year to map, or None for "latest available".
    """
    d = df.dropna(subset=['Water_Stress_Total_Pct'])
    if year is None:
        d = d.sort_values('Year').groupby('ISO3_Code').tail(1)
        title = title or 'Water stress by country (latest available year)'
    else:
        d = d[d['Year'] == year]
        title = title or f'Water stress by country, {year}'
    fig = px.choropleth(
        d, locations='ISO3_Code', color='Water_Stress_Category', hover_name='Country',
        hover_data={'ISO3_Code': False, 'Year': True, 'Water_Stress_Total_Pct': ':.1f',
                    'Water_Stress_Category': False},
        color_discrete_map=TIER_COLORS, category_orders={'Water_Stress_Category': TIER_ORDER},
        labels={'Water_Stress_Total_Pct': 'Stress (%)'})
    return _layout(fig, title, 'UN SDG 6.4.2 tier')


def stress_tier_animation(df, title='Water stress by country, 2001–2023'):
    """Animated tier map with a year slider (interactive HTML only)."""
    d = df.dropna(subset=['Water_Stress_Total_Pct']).sort_values('Year')
    # Every tier must appear in every frame or Plotly drops its legend colour
    pad = pd.DataFrame([{'Year': y, 'ISO3_Code': None, 'Country': '', 'Water_Stress_Category': t,
                         'Water_Stress_Total_Pct': np.nan}
                        for y in d['Year'].unique() for t in TIER_ORDER[:-1]])
    d = pd.concat([d, pad], ignore_index=True)
    fig = px.choropleth(
        d, locations='ISO3_Code', color='Water_Stress_Category', hover_name='Country',
        animation_frame='Year', hover_data={'ISO3_Code': False, 'Water_Stress_Total_Pct': ':.1f'},
        color_discrete_map=TIER_COLORS, category_orders={'Water_Stress_Category': TIER_ORDER},
        labels={'Water_Stress_Total_Pct': 'Stress (%)'})
    return _layout(fig, title, 'UN SDG 6.4.2 tier')


def continuous_map(d, column, title, colorbar_title, log=False, scale='YlGnBu', hover=None, range_color=None):
    """Generic continuous choropleth for one value per country.

    Args:
        d: one row per country with ISO3_Code, Country and `column`.
        log: colour on a log10 scale (labels still show real values).
        hover: extra columns to show on hover, {column: format}.
    """
    d = d.dropna(subset=[column]).copy()
    color_col = column
    if log:
        d = d[d[column] > 0]
        d['_log'] = np.log10(d[column])
        color_col = '_log'
    hover_data = {'ISO3_Code': False, column: ':.1f', **(hover or {})}
    if log:
        hover_data['_log'] = False
    fig = px.choropleth(d, locations='ISO3_Code', color=color_col, hover_name='Country',
                        hover_data=hover_data, color_continuous_scale=scale, range_color=range_color)
    if log:
        lo, hi = np.floor(d['_log'].min()), np.ceil(d['_log'].max())
        ticks = np.arange(lo, hi + 1)
        fig.update_coloraxes(colorbar=dict(tickvals=ticks, ticktext=[f'{10 ** t:g}' for t in ticks]))
    fig.update_coloraxes(colorbar_title_text=colorbar_title)
    return _layout(fig, title)


def categorical_map(d, column, title, colors, order, legend_title, hover=None):
    """Generic categorical choropleth for one label per country."""
    fig = px.choropleth(d, locations='ISO3_Code', color=column, hover_name='Country',
                        hover_data={'ISO3_Code': False, column: False, **(hover or {})},
                        color_discrete_map=colors, category_orders={column: order})
    return _layout(fig, title, legend_title)


def save_map(fig, out_dir, name, width=1100, height=560):
    """Save a map as interactive HTML and static PNG; return the PNG path.

    The PNG is what renders on GitHub and in the report; the HTML keeps hover
    and zoom for presentations and the dashboard.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.write_html(out_dir / f'{name}.html', include_plotlyjs='cdn')
    png = out_dir / f'{name}.png'
    fig.write_image(png, width=width, height=height, scale=1.5)
    return png
