import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ------------------------
# Page layout and CSS
# ------------------------
# st.set_page_config(layout="wide")

# Custom padding via CSS (left 10px, right 50px, top 10px)
st.markdown(
    """
    <style>
    .reportview-container {
        padding-left: 10px;
        padding-right: 100px;
        padding-top: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🏪 Warehouse-Cluster Geo Dashboard")

# ------------------------
# CSV Upload
# ------------------------
uploaded_file = st.file_uploader("Upload your warehouse-cluster CSV", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # Convert coordinates to float
    df['latitude'] = df['latitude'].astype(float)
    df['longitude'] = df['longitude'].astype(float)
    df['wh_lat'] = df['wh_lat'].astype(float)
    df['wh_long'] = df['wh_long'].astype(float)
    df['distance_km'] = df['distance_km'].astype(float)
    df['dist_from_wh'] = df['dist_from_wh'].astype(float)

    # ------------------------
    # Warehouse selection on top
    # ------------------------
    warehouses = df['warehouse_name'].unique()
    selected_warehouse = st.selectbox("Select Warehouse", warehouses)

    wh_data = df[df['warehouse_name'] == selected_warehouse]
    if wh_data.empty:
        st.warning("No cluster data for this warehouse.")
        st.stop()

    wh_lat = wh_data.iloc[0]['wh_lat']
    wh_long = wh_data.iloc[0]['wh_long']

    # ------------------------
    # Aggregate cluster info for centroids
    # ------------------------
    cluster_data = wh_data.groupby('k_means').agg({
        'latitude': 'mean',
        'longitude': 'mean',
        'partner_gmv': 'sum',
        'distance_km': 'mean',
        'customer_id': 'count',
        'cx_status': lambda x: list(x)
    }).reset_index()

    # Precompute cluster summary info for hover
    cluster_data['transacting_count'] = cluster_data['cx_status'].apply(lambda x: x.count('Transacting'))
    cluster_data['non_transacting_count'] = cluster_data['cx_status'].apply(lambda x: x.count('Non-Transacting'))

    # ------------------------
    # Cluster summary table
    # ------------------------
    cluster_summary = wh_data.groupby('k_means').agg(
        transacting_count=('cx_status', lambda x: (x=='Transacting').sum()),
        non_transacting_count=('cx_status', lambda x: (x=='Non-Transacting').sum()),
        avg_pgmv_transacting=('partner_gmv', lambda x: x[wh_data.loc[x.index,'cx_status']=='Transacting'].mean()),
        avg_pgmv_nontransacting=('partner_gmv', lambda x: x[wh_data.loc[x.index,'cx_status']=='Non-Transacting'].mean()),
        avg_dist_transacting=('dist_from_wh', lambda x: x[wh_data.loc[x.index,'cx_status']=='Transacting'].mean()),
        avg_dist_nontransacting=('dist_from_wh', lambda x: x[wh_data.loc[x.index,'cx_status']=='Non-Transacting'].mean())
    ).reset_index()

    # ------------------------
    # Plotly Map
    # ------------------------
    fig = go.Figure()

    # Cluster centroids (blue)
    fig.add_trace(go.Scattermapbox(
        lat=cluster_data['latitude'],
        lon=cluster_data['longitude'],
        mode='markers+text',
        marker=dict(size=20, color='blue', opacity=0.9),
        text=[f"Cluster {c}" for c in cluster_data['k_means']],
        textfont=dict(color='black', size=12),
        hovertext=[
            f"Cluster: {row['k_means']}<br>"
            f"Transacting CX: {row['transacting_count']}<br>"
            f"Non-Transacting CX: {row['non_transacting_count']}<br>"
            f"Avg distance_km: {row['distance_km']:.2f}<br>"
            f"Total GMV: {row['partner_gmv']:.2f}"
            for _, row in cluster_data.iterrows()
        ],
        hoverinfo='text',
        name='Clusters'
    ))

    # Lines from warehouse → clusters
    for _, row in cluster_data.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[wh_lat, row['latitude']],
            lon=[wh_long, row['longitude']],
            mode='lines',
            line=dict(width=2, color='gray'),
            hoverinfo='none',
            showlegend=False
        ))

    # Customer nodes - single trace per type
    transacting = wh_data[wh_data['cx_status']=='Transacting']
    non_transacting = wh_data[wh_data['cx_status']=='Non-Transacting']

    # Transacting CX
    fig.add_trace(go.Scattermapbox(
        lat=transacting['latitude'],
        lon=transacting['longitude'],
        mode='markers',
        marker=dict(size=8, color='green', opacity=0.8),
        text=(
            "Customer: " + transacting['customer_id'].astype(str) + "<br>" +
            "Last Order: " + transacting['last_order_date'].astype(str) + "<br>" +
            "Distance from WH: " + transacting['dist_from_wh'].round(2).astype(str) + " km<br>" +
            "PGMV: " + transacting['partner_gmv'].round(2).astype(str) + "<br>" +
            "Cluster: " + transacting['k_means'].astype(str)
        ),
        hoverinfo='text',
        name='Transacting CX'
    ))

    # Non-Transacting CX
    fig.add_trace(go.Scattermapbox(
        lat=non_transacting['latitude'],
        lon=non_transacting['longitude'],
        mode='markers',
        marker=dict(size=8, color='red', opacity=0.8),
        text=(
            "Customer: " + non_transacting['customer_id'].astype(str) + "<br>" +
            "Last Order: " + non_transacting['last_order_date'].astype(str) + "<br>" +
            "Distance from WH: " + non_transacting['dist_from_wh'].round(2).astype(str) + " km<br>" +
            "PGMV: " + non_transacting['partner_gmv'].round(2).astype(str) + "<br>" +
            "Cluster: " + non_transacting['k_means'].astype(str)
        ),
        hoverinfo='text',
        name='Non-Transacting CX'
    ))

    # Map layout
    # --- Additional uploaded customer file (pre-clustered) ---
    cust_file = st.file_uploader("Upload customer locations (must include 'cluster_customer', cust_id, lat, long, max_pgmv)", type=["csv","xlsx"], key="cust_file")
    if cust_file is not None:
        try:
            if str(cust_file.name).lower().endswith('.xlsx'):
                cust_df = pd.read_excel(cust_file)
            else:
                cust_df = pd.read_csv(cust_file)
        except Exception as e:
            st.error(f"Failed to read uploaded customer file: {e}")
            cust_df = None

        if cust_df is not None:
            # Normalize column names
            lower_map = {c.lower(): c for c in cust_df.columns}
            cluster_col = lower_map.get('cluster_customer') or lower_map.get('cluster') or lower_map.get('cust_cluster')
            id_col = lower_map.get('cust_id') or lower_map.get('customer_id')
            lat_col = lower_map.get('lat') or lower_map.get('latitude')
            long_col = lower_map.get('long') or lower_map.get('longitude')
            pgmv_col = lower_map.get('max pgmv')

            if cluster_col is None or id_col is None or lat_col is None or long_col is None:
                st.error("Uploaded file must contain: cluster_customer (or cluster), cust_id (or customer_id), lat (or latitude), and long (or longitude).")
            else:
                try:
                    # Cast types and normalize column names
                    cust_df[lat_col] = cust_df[lat_col].astype(float)
                    cust_df[long_col] = cust_df[long_col].astype(float)
                    cust_df[id_col] = cust_df[id_col].astype(str)
                    cust_df[cluster_col] = cust_df[cluster_col].astype(str)
                    if pgmv_col is not None:
                        cust_df[pgmv_col] = pd.to_numeric(cust_df[pgmv_col], errors='coerce').fillna(0.0)

                    cust_df = cust_df.rename(columns={id_col: 'cust_id', lat_col: 'lat', long_col: 'long', cluster_col: 'cluster_customer'})
                    if pgmv_col is not None:
                        cust_df = cust_df.rename(columns={pgmv_col: 'max_pgmv'})
                    else:
                        cust_df['max_pgmv'] = 0.0

                    # Color palette
                    color_list = ['orange', 'purple', 'magenta', 'yellow', 'cyan', 'brown', 'teal', 'pink', 'black', 'green']

                    # Map cluster values to colors
                    unique_clusters = sorted(cust_df['cluster_customer'].unique())
                    color_map = {c: color_list[i % len(color_list)] for i, c in enumerate(unique_clusters)}

                    # Plot each cluster's points using same color and uniform legend label 'Cust_Cluster'
                    # for i, c in enumerate(unique_clusters):
                    # cdf = cust_df[cust_df['cluster_customer'] == c]
                    color = 'orange'
                    fig.add_trace(go.Scattermapbox(
                        lat=cust_df['lat'],
                        lon=cust_df['long'],
                        mode='markers',
                        marker=dict(size=7, color=color, opacity=0.7),
                        text=(
                            "Cluster: " + cust_df['cluster_customer'].astype(str) + "<br>" +
                            "Cust ID: " + cust_df['cust_id'].astype(str) + "<br>" +
                            "Lat: " + cust_df['lat'].round(6).astype(str) + "<br>" +
                            "Long: " + cust_df['long'].round(6).astype(str) + "<br>" +
                            "Max PGMV: " + cust_df['max_pgmv'].round(2).astype(str)
                        ),
                        hoverinfo='text',
                        name='Cust_Id'
                    ))

                    # Compute centroids (avg lat/long) and avg max_pgmv per cluster
                    centroids = cust_df.groupby('cluster_customer').agg(
                        cen_lat=('lat', 'mean'),
                        cen_long=('long', 'mean'),
                        avg_pgmv=('max_pgmv', 'mean')
                    ).reset_index()

                    # Plot centroids with same cluster color, hover shows cluster number and avg max pgmv

                    fig.add_trace(go.Scattermapbox(
                        lat=centroids['cen_lat'],
                        lon=centroids['cen_long'],
                        mode='markers+text',
                        marker=dict(size=20, color='black', opacity=0.9),
                        text=[f"Cluster {c}" for c in centroids['cluster_customer']],
                        textfont=dict(color='black', size=12),
                        # hovertext=[f"Cluster: {row['cluster_customer']}<br>Avg max PGMV: {row['max_pgmv']:.2f}" for _,row in centroids.iterrows()],
                        hoverinfo='text',
                        name='Cust_Cluster'
                    ))

                    # Optional: show uploaded cluster summary
                    st.markdown("### Uploaded Customers: Cluster Summary")
                    summary = cust_df.groupby('cluster_customer').agg(
                        customers=('cust_id', 'count'),
                        lat=('lat', 'mean'),
                        long = ('long', 'mean'),
                        avg_pgmv=('max_pgmv', 'mean')
                    ).reset_index()
                    st.dataframe(summary, use_container_width=True)
                except Exception as e:
                    st.error(f"Error processing uploaded customer file: {e}")

    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=8,
        mapbox_center={"lat": wh_lat, "lon": wh_long},
        height=700, width=10000,
#         margin={"r":0,"t":0,"l":0,"b":0},
#         showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    # Cluster summary table - full width
    st.markdown("### Cluster Summary")
    st.dataframe(cluster_summary, use_container_width=True)

else:
    st.info("Please upload a CSV file to continue.")
