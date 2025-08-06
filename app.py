import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from utils import load_update_table

# Start the Dash app
app = dash.Dash(__name__)
server = app.server
app.title = "Methane Emissions Dashboard"

emissions_df = load_update_table("ghg.EF_W_EMISSIONS_SOURCE_GHG", folder='epa')
facilities_df = load_update_table("ghg.rlps_ghg_emitter_facilities", folder='epa')

columns_required = [
    'facility_id',
    'reporting_year',
    'industry_segment',
    'reporting_category',
    'total_reported_ch4_emissions',
    'basin_associated_with_facility'
]
emissions_df = emissions_df[columns_required].copy()
emissions_df.dropna(subset=['reporting_year', 'industry_segment', 'total_reported_ch4_emissions'], inplace=True)

emissions_df['reporting_year'] = emissions_df['reporting_year'].astype(int)
emissions_df['total_reported_ch4_emissions'] = emissions_df['total_reported_ch4_emissions'].astype(float)

_df = emissions_df['basin_associated_with_facility'].fillna('Unknown').astype(str).str.strip().replace('', 'Unknown')
emissions_df['basin_associated_with_facility'] = _df.str.title()

fig1_segments = sorted(emissions_df['industry_segment'].unique())
fig2_sources = sorted(emissions_df['reporting_category'].dropna().unique())

year_min = emissions_df['reporting_year'].min()
year_max = emissions_df['reporting_year'].max()

unique_basins = sorted(b for b in emissions_df['basin_associated_with_facility'].unique() if b != 'Unknown')
basin_options = [{'label': 'All Basins', 'value': 'All'}] + \
                [{'label': basin, 'value': basin} for basin in unique_basins] + \
                [{'label': 'Unknown', 'value': 'Unknown'}]

app.layout = html.Div([
    html.H1("U.S. EPA Methane Emissions Dashboard", style={"textAlign": "center", "fontFamily": "Arial", "fontSize": "36px", "color": "#2C3E50"}),

    html.Div([html.Label("Select Basin:", style={
            "fontWeight": "600", "fontFamily": "Arial, sans-serif", "fontSize": "16px", "color": "#34495E", "marginBottom": "5px"}),
             dcc.Dropdown(id='basin-dropdown', options=basin_options, value='All', clearable=False, style={"width": "100%", "fontFamily": "Arial, sans-serif", "fontSize": "14px"})], style={'width': '300px', 'margin': 'auto'}),

    html.Div([html.Label("Select Year Range:", style={"fontWeight": "600", "fontFamily": "Arial", "marginTop": "20px"}),
             dcc.RangeSlider(id='year-range', min=year_min, max=year_max, value=[year_min, year_max], marks={str(y): str(y) for y in range(year_min, year_max+1, 2)}, step=1, tooltip={"always_visible": True})], style={'width': '80%', 'margin': 'auto'}),

    dcc.Graph(id='emissions-graph', style={'marginTop': '30px'}),

    html.H2("Methane Emissions vs. Company (Stacked by Emission Source)", style={"textAlign": "center", "fontFamily": "Arial", "fontSize": "36px", "color": "#2C3E50"}),
    dcc.Graph(id='emissions-source-graph', style={'marginTop': '20px'}),

    html.H2("Heat map of methane emissions by state", style={"textAlign": "center", "fontFamily": "Arial", "fontSize": "36px", "color": "#2C3E50"}),
    dcc.Graph(id='state-heatmap', style={'marginTop': '20px'})
])

def filter_df(selected_years, selected_basin):
    dff = emissions_df[(emissions_df['reporting_year'] >= selected_years[0]) & (emissions_df['reporting_year'] <= selected_years[1])]
    if selected_basin != 'All':
        dff = dff[dff['basin_associated_with_facility'] == selected_basin]
    return dff

@app.callback(
    Output('emissions-graph', 'figure'),
    Output('emissions-source-graph', 'figure'),
    Output('state-heatmap', 'figure'),
    Input('year-range', 'value'),
    Input('basin-dropdown', 'value')
)
def update_all(selected_years, selected_basin):
    # Figure 1: Industry Segment
    dff = filter_df(selected_years, selected_basin)
    g1 = dff.groupby(['reporting_year', 'industry_segment'])['total_reported_ch4_emissions'].sum().reset_index()
    p1 = g1.pivot(index='reporting_year', columns='industry_segment', values='total_reported_ch4_emissions').fillna(0).reindex(columns=fig1_segments, fill_value=0)
    fig1 = go.Figure(); [fig1.add_trace(go.Bar(x=p1.index, y=p1[seg], name=seg)) for seg in fig1_segments]
    fig1.update_layout(barmode='stack', title='Methane Emissions vs Year (Stacked by Industry Segment)', xaxis_title='Year', yaxis_title='Methane Emissions (tons)', legend_title='Industry Segment', height=600, margin=dict(t=60,b=40,l=40,r=40))

    # Figure 2: Company by Emission Source
    m2 = dff.merge(facilities_df[['facility_id','parent_company']], on='facility_id', how='left')
    top_co = m2.groupby('parent_company')['total_reported_ch4_emissions'].sum().nlargest(20).index
    m2 = m2[m2['parent_company'].isin(top_co)]
    g2 = m2.groupby(['parent_company','reporting_category'])['total_reported_ch4_emissions'].sum().reset_index()
    p2 = g2.pivot(index='parent_company', columns='reporting_category', values='total_reported_ch4_emissions').fillna(0).loc[lambda df: df.sum(axis=1).sort_values(ascending=False).index]
    fig2 = go.Figure(); [fig2.add_trace(go.Bar(x=p2.index, y=p2[src], name=src)) for src in fig2_sources if src in p2]
    fig2.update_layout(barmode='stack', title='Methane Emissions vs. Company (Stacked by Emission Source)', xaxis_title='Company Name', yaxis_title='Methane Emissions (Total CH4 Emissions)', legend_title='Emission Source', height=500, margin=dict(t=60,b=200,l=40,r=40))

    # Figure 3: Heatmap by State

    m3 = dff.merge(facilities_df[['facility_id','state']], on='facility_id', how='left')
    g3 = m3.groupby(['state','reporting_category'])['total_reported_ch4_emissions'].sum().reset_index()

    top_cats = g3.groupby('reporting_category')['total_reported_ch4_emissions'].sum().nlargest(15).index
    g3 = g3[g3['reporting_category'].isin(top_cats)]

    p3 = g3.pivot(index='state', columns='reporting_category', values='total_reported_ch4_emissions').fillna(0)
    z = np.log1p(p3.values)

    fig3 = go.Figure(data=go.Heatmap(
        z=z,
        x=p3.columns,
        y=p3.index,
        coloraxis='coloraxis'
    ))
    fig3.update_layout(
        title='Heat map of methane emissions by state',
        xaxis_title='Emission Source', yaxis_title='State',
        coloraxis_colorbar=dict(title='Log(Emissions+1)'),
        width=1600, height=800,
        xaxis=dict(tickangle=45, automargin=True),
        margin=dict(t=80,b=200,l=120,r=100)
    )

    return fig1, fig2, fig3

if __name__ == '__main__':
    app.run(debug=True)