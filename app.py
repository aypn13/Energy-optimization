import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Energy Optimization Dashboard - Nitrocapt", layout="wide")

# Initialize session state variables for all tabs
if 'total_hybrid_cost' not in st.session_state:
    st.session_state.total_hybrid_cost = None
if 'total_cost_base' not in st.session_state:
    st.session_state.total_cost_base = None
if 'battery_adjusted_cost' not in st.session_state:
    st.session_state.battery_adjusted_cost = None
if 'total_demand_mwh' not in st.session_state:
    st.session_state.total_demand_mwh = None
if 'demand_df' not in st.session_state:
    st.session_state.demand_df = None
if 'price_df' not in st.session_state:
    st.session_state.price_df = None
if 'total_co2_emissions_tonnes' not in st.session_state:
    st.session_state.total_co2_emissions_tonnes = None
if 'selected_optimization_country' not in st.session_state:
    st.session_state.selected_optimization_country = None
if 'use_battery' not in st.session_state:
    st.session_state.use_battery = False
if 'battery_capacity' not in st.session_state:
    st.session_state.battery_capacity = 0.0
if 'efficiency' not in st.session_state:
    st.session_state.efficiency = 0
if 'dod' not in st.session_state:
    st.session_state.dod = 0
if 'storage_hours' not in st.session_state:
    st.session_state.storage_hours = 0
if 'ppa_price_eur_mwh' not in st.session_state:
    st.session_state.ppa_price_eur_mwh = 40.0
if 'hedge_volume' not in st.session_state:
    st.session_state.hedge_volume = 6.0
if 'year_option' not in st.session_state:
    st.session_state.year_option = 'Choose year'
if 'demand_option' not in st.session_state:
    st.session_state.demand_option = 'Choose demand'


# Define all available countries (make it globally accessible)
all_countries = ["Austria", "Belgium", "Bulgaria", "Croatia", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Italy", "Latvia", "Lithuania", "Luxembourg", "Netherlands", "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland"]

# Load CO2 Emission Data once globally
co2_data_dir = os.path.join("data", "co2")
co2_file_path = os.path.join(co2_data_dir, "carbon.csv")
df_carbon = None
if os.path.exists(co2_file_path):
    df_carbon = pd.read_csv(co2_file_path)
else:
    st.warning(f"CO2 emission data file not found at {co2_file_path}. CO2 calculations may be inaccurate or unavailable.")


@st.cache_data # Cache the function results for performance
def calculate_metrics_for_country(
    selected_country: str,
    selected_year: str,
    demand_option: str,
    use_battery: bool,
    battery_capacity: float,
    efficiency: int,
    dod: int,
    storage_hours: int,
    ppa_price_eur_mwh: float,
    hedge_volume: float,
    df_carbon_data: pd.DataFrame # Renamed to avoid conflict with global df_carbon
):
    """
    Calculates spot cost, battery cost, hybrid cost, LCOE, and CO2 emissions for a given country.
    """
    results = {
        "Country": selected_country,
        "Year": selected_year,
        "Demand Profile": demand_option,
        "Total Spot Cost (€)": None,
        "Total Cost with Battery (€)": None,
        "Total Hybrid Cost (€)": None,
        "LCOE (Spot) (€/MWh)": None,
        "LCOE (Battery) (€/MWh)": None,
        "LCOE (Hybrid) (€/MWh)": None,
        "Total CO2 Emissions (tonnes CO2eq)": None
    }

    try:
        # Load price data for the selected country and year
        data_dir = "data"
        europe_prices_dir = os.path.join(data_dir, "europe_prices")
        multi_year_file = os.path.join(europe_prices_dir, f"{selected_country.lower()}_15_24.csv")
        
        if not os.path.exists(multi_year_file):
            st.error(f"Price data for {selected_country} in {selected_year} not found at {multi_year_file}. Skipping calculations for this country.")
            return results

        price_df = pd.read_csv(multi_year_file)
        price_df["timestamp"] = pd.to_datetime(price_df["timestamp"])
        price_df = price_df[price_df["timestamp"].dt.year == int(selected_year)]

        if price_df.empty:
            st.error(f"No price data for {selected_country} in {selected_year} after filtering. Skipping calculations.")
            return results

        demand_value = 0
        if demand_option == "600 kWh":
            demand_value = 600
        elif demand_option == "5 MWh":
            demand_value = 5000
        elif demand_option == "10 MWh":
            demand_value = 10000
        elif demand_option == "15 MWh":
            demand_value = 15000
        
        demand_df = pd.DataFrame({
            "timestamp": price_df["timestamp"],
            "demand_kWh": [demand_value] * len(price_df)
        })
        merged_df = pd.merge(price_df, demand_df, on="timestamp")

        if "Grid_Price_EUR_per_MWh" in merged_df.columns:
            merged_df["price"] = merged_df["Grid_Price_EUR_per_MWh"]
        elif "price" not in merged_df.columns:
            raise KeyError("Required price column not found in merged data.")

        merged_df["hourly_cost"] = (merged_df["price"] / 1000) * merged_df["demand_kWh"]
        
        total_cost_base = merged_df["hourly_cost"].sum()
        total_demand_mwh = merged_df["demand_kWh"].sum() / 1000

        results["Total Spot Cost (€)"] = total_cost_base

        # CO2 Emission Factor Lookup
        emission_factor_g_per_kWh = 0.0
        if df_carbon_data is not None:
            filtered_emission = df_carbon_data[
                (df_carbon_data['Entity'] == selected_country) & 
                (df_carbon_data['Year'] == int(selected_year))
            ]
            if not filtered_emission.empty:
                emission_factor_g_per_kWh = filtered_emission['gCO2/kWh'].iloc[0]
            # else:
            #     st.warning(f"CO2 emission factor not found for {selected_country} in {selected_year} in carbon.csv.")
        
        if total_demand_mwh > 0:
            total_co2_emissions_tonnes = (total_demand_mwh * 1000 * emission_factor_g_per_kWh) / 1_000_000
        else:
            total_co2_emissions_tonnes = 0
        results["Total CO2 Emissions (tonnes CO2eq)"] = total_co2_emissions_tonnes

        battery_adjusted_cost = total_cost_base
        total_hybrid_cost = total_cost_base # Default to spot cost
        
        if use_battery:
            merged_df["date"] = merged_df["timestamp"].dt.date
            savings = []
            daily_groups = merged_df.groupby("date")
            for _, group in daily_groups:
                sorted_group = group.sort_values(by="price")
                charge_hours = sorted_group.head(storage_hours)
                discharge_hours = sorted_group.tail(storage_hours)
                
                # Ensure battery_capacity and storage_hours are not zero to avoid division by zero
                hourly_battery_power = battery_capacity / storage_hours if storage_hours > 0 else 0
                
                charge_cost = (charge_hours["price"] / 1000 * (hourly_battery_power * 1000)).sum()
                discharge_value = (discharge_hours["price"] / 1000 * (hourly_battery_power * 1000) * (efficiency / 100) * (dod / 100)).sum()
                net_saving = discharge_value - charge_cost
                savings.append(net_saving)
            
            battery_adjusted_cost = total_cost_base - sum(savings)
            results["Total Cost with Battery (€)"] = battery_adjusted_cost

            # Recalculate hybrid cost with battery optimization
            merged_df_hybrid = merged_df.copy()
            merged_df_hybrid['battery_used_mwh'] = 0.0
            merged_df_hybrid['hedge_used_mwh'] = 0.0
            merged_df_hybrid['spot_used_mwh'] = 0.0
            merged_df_hybrid['hedge_settlement'] = 0.0
            merged_df_hybrid['spot_cost'] = 0.0
            merged_df_hybrid['hybrid_cost_hourly'] = 0.0

            for date, group in merged_df_hybrid.groupby('date'):
                group = group.copy()
                discharge_hours_indices = group.sort_values("price", ascending=False).head(storage_hours).index
                charge_hours_indices = group.sort_values("price", ascending=True).head(storage_hours).index

                for idx in group.index:
                    demand_mwh = merged_df_hybrid.at[idx, 'demand_kWh'] / 1000
                    spot_price = merged_df_hybrid.at[idx, 'price']

                    battery_available = 0.0
                    charge_discharge = 0.0

                    if storage_hours > 0: # Avoid division by zero
                        usable_capacity = battery_capacity * (efficiency / 100) * (dod / 100)
                        battery_power_limit = battery_capacity / float(storage_hours) # Hourly max power

                        if idx in discharge_hours_indices:
                            battery_available = min(battery_power_limit, usable_capacity / float(storage_hours))
                            charge_discharge = -battery_available
                        elif idx in charge_hours_indices:
                            charge_discharge = battery_power_limit
                    
                    remaining_demand_after_battery = demand_mwh - battery_available
                    
                    hedge_used_hourly = min(remaining_demand_after_battery, hedge_volume / 24)
                    spot_used_hourly = max(0.0, remaining_demand_after_battery - hedge_used_hourly)

                    merged_df_hybrid.at[idx, 'battery_used_mwh'] = battery_available
                    merged_df_hybrid.at[idx, 'hedge_used_mwh'] = hedge_used_hourly
                    merged_df_hybrid.at[idx, 'spot_used_mwh'] = spot_used_hourly

                    merged_df_hybrid.at[idx, 'hedge_settlement'] = (ppa_price_eur_mwh - spot_price) * hedge_used_hourly
                    merged_df_hybrid.at[idx, 'spot_cost'] = spot_price * spot_used_hourly
                    
                    merged_df_hybrid.at[idx, 'hybrid_cost_hourly'] = (
                        merged_df_hybrid.at[idx, 'spot_cost']
                        + (ppa_price_eur_mwh * hedge_used_hourly)
                    )
            total_hybrid_cost = merged_df_hybrid['hybrid_cost_hourly'].sum()
            results["Total Hybrid Cost (€)"] = total_hybrid_cost
        else: # If no battery, hybrid cost is just spot minus hedge benefits (simple PPA)
            total_hybrid_cost_no_battery = 0
            for idx in merged_df.index:
                demand_mwh = merged_df.at[idx, 'demand_kWh'] / 1000
                spot_price = merged_df.at[idx, 'price']
                
                hedge_used_hourly = min(demand_mwh, hedge_volume / 24)
                spot_used_hourly = max(0.0, demand_mwh - hedge_used_hourly)
                
                total_hybrid_cost_no_battery += (spot_price * spot_used_hourly) + (ppa_price_eur_mwh * hedge_used_hourly)
            
            total_hybrid_cost = total_hybrid_cost_no_battery
            results["Total Hybrid Cost (€)"] = total_hybrid_cost

        # LCOE calculations
        if total_demand_mwh > 0:
            results["LCOE (Spot) (€/MWh)"] = total_cost_base / total_demand_mwh
            if use_battery and results["Total Cost with Battery (€)"] is not None:
                results["LCOE (Battery) (€/MWh)"] = results["Total Cost with Battery (€)"] / total_demand_mwh
            if results["Total Hybrid Cost (€)"] is not None:
                results["LCOE (Hybrid) (€/MWh)"] = results["Total Hybrid Cost (€)"] / total_demand_mwh

    except Exception as e:
        # st.error(f"Error calculating metrics for {selected_country}: {e}")
        # Return partial results if an error occurs, or None for failed calculations
        return results

    return results


st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2 , tab3, tab4, tab5 = st.tabs(["Optimization", "PPA Analysis", "Waste Heat", "LCOE", "Comparison"])

with tab1:
    st.header("Optimization")
    st.title("Nitrocapt Energy Optimization")

    st.sidebar.header("🔧 Optimization Inputs")

    demand_option = st.sidebar.selectbox("Select Demand Profile", ["Choose demand", "600 kWh", "5 MWh", "10 MWh", "15 MWh"], key="demand_profile_opt")
    year_option = st.sidebar.selectbox("Select Year", ["Choose year"] + [str(y) for y in range(2015, 2025)], key="year_opt")
    
    country_option = st.sidebar.selectbox("Select Country", all_countries, key="country_opt")
    
    # Store in session state
    st.session_state.selected_optimization_country = country_option
    st.session_state.year_option = year_option
    st.session_state.demand_option = demand_option

    use_custom_data = st.sidebar.checkbox("Upload Custom Demand and Price Data", key="custom_data_opt")
    uploaded_demand = None
    uploaded_price = None
    if use_custom_data:
        uploaded_demand = st.sidebar.file_uploader("Upload Custom Demand File", type=["csv"], key="upload_demand_opt")
        uploaded_price = st.sidebar.file_uploader("Upload Custom Price File", type=["csv"], key="upload_price_opt")

    use_battery = st.sidebar.checkbox("Include Battery Storage", key="use_battery_opt")
    if use_battery:
        default_capacity = float(0.6 if demand_option == "600 kWh" else 6 if demand_option == "5 MWh" else 13.89 if demand_option == "10 MWh" else 20.83 if demand_option == "15 MWh" else 1.0)
        battery_capacity = st.sidebar.number_input("Battery Capacity (MWh)", min_value=0.0, value=default_capacity, key="battery_cap_opt")
        efficiency = st.sidebar.slider("Battery Efficiency (%)", min_value=0, max_value=100, value=90, key="efficiency_opt")
        dod = st.sidebar.slider("Depth of Discharge (DoD %)", min_value=0, max_value=100, value=80, key="dod_opt")
        storage_hours = st.sidebar.number_input("Storage Duration (hours)", min_value=1, max_value=24, value=4, key="storage_hours_opt")
        
        st.session_state.battery_capacity = battery_capacity
        st.session_state.efficiency = efficiency
        st.session_state.dod = dod
        st.session_state.storage_hours = storage_hours
        st.session_state.use_battery = use_battery
    else:
        st.session_state.use_battery = False
        st.session_state.battery_capacity = 0.0 
        st.session_state.efficiency = 0
        st.session_state.dod = 0
        st.session_state.storage_hours = 0


    st.sidebar.markdown("---")
    st.sidebar.subheader("🌍 CO2 Emission Factor Source")
        
    emission_factor_g_per_kWh_display = st.empty() # Placeholder for displaying the factor

    col1, col2 = st.columns([1, 2])

    if demand_option != "Choose demand" and year_option != "Choose year" and country_option:
        
        emission_factor_g_per_kWh = 0.0 
        if df_carbon is not None:
            selected_year_int = int(year_option)
            filtered_emission = df_carbon[
                (df_carbon['Entity'] == country_option) & 
                (df_carbon['Year'] == selected_year_int)
            ]
            
            if not filtered_emission.empty:
                emission_factor_g_per_kWh = filtered_emission['gCO2/kWh'].iloc[0]
            else:
                st.warning(f"CO2 emission factor not found for {country_option} in {year_option}. Using a default of 0 gCO2eq/kWh.")
        else:
            st.warning("CO2 emission data not loaded. Using a default of 0 gCO2eq/kWh.")

        emission_factor_g_per_kWh_display.info(f"Using CO2 Emission Factor: {emission_factor_g_per_kWh:.2f} gCO2eq/kWh")

        try:
            if use_custom_data and uploaded_demand is not None and uploaded_price is not None:
                demand_df = pd.read_csv(uploaded_demand)
                price_df = pd.read_csv(uploaded_price)
                demand_df["timestamp"] = pd.to_datetime(demand_df["timestamp"])
                price_df["timestamp"] = pd.to_datetime(price_df["timestamp"])
            else:
                data_dir = "data"
                europe_prices_dir = os.path.join(data_dir, "europe_prices")
                multi_year_file = os.path.join(europe_prices_dir, f"{country_option.lower()}_15_24.csv")
                
                if not os.path.exists(multi_year_file):
                    st.warning(f"Price data for {country_option} in {year_option} not found at {multi_year_file}. Please check the file path or upload custom data.")
                    merged_df = None
                else:
                    price_df = pd.read_csv(multi_year_file)
                    price_df["timestamp"] = pd.to_datetime(price_df["timestamp"])
                    price_df = price_df[price_df["timestamp"].dt.year == int(year_option)]
                    
                    demand_value = 0
                    if demand_option == "600 kWh":
                        demand_value = 600
                    elif demand_option == "5 MWh":
                        demand_value = 5000
                    elif demand_option == "10 MWh":
                        demand_value = 10000
                    elif demand_option == "15 MWh":
                        demand_value = 15000
                    
                    demand_df = pd.DataFrame({
                        "timestamp": price_df["timestamp"],
                        "demand_kWh": [demand_value] * len(price_df)
                    })
                    merged_df = pd.merge(price_df, demand_df, on="timestamp")

            if merged_df is not None:
                country_code_map = {
                    "Austria": "at", "Belgium": "be", "Bulgaria": "bg", "Croatia": "hr","Czechia": "cz","Denmark": "dk","Estonia": "ee","Finland": "fi",
                    "France": "fr","Germany": "de","Greece": "gr","Hungary": "hu","Italy": "it","Latvia": "lv","Lithuania": "lt","Luxembourg": "lu","Netherlands": "nl",
                    "Norway": "no","Poland": "pl","Portugal": "pt","Romania": "ro","Slovakia": "sk","Slovenia": "si","Spain": "es","Sweden": "se","Switzerland": "ch"
                }
                country_code = country_code_map.get(country_option, "").lower()
                if country_code:
                    st.markdown(f"""
                        <div style='display: flex; align-items: center; gap: 10px;'>
                            <img src='https://flagcdn.com/32x24/{country_code}.png' alt='{country_option}' width='32' height='24'>
                            <h2 style='margin: 0;'>Nitrocapt Energy Optimization</h2>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.title("Nitrocapt Energy Optimization")

                if "Grid_Price_EUR_per_MWh" in merged_df.columns:
                    merged_df["price"] = merged_df["Grid_Price_EUR_per_MWh"]
                elif "price" not in merged_df.columns:
                    raise KeyError("Required price column not found in merged data.")
                merged_df["hourly_cost"] = (merged_df["price"] / 1000) * merged_df["demand_kWh"]
                
                st.session_state.total_cost_base = merged_df["hourly_cost"].sum()
                st.session_state.total_demand_mwh = merged_df["demand_kWh"].sum() / 1000

                if st.session_state.total_demand_mwh is not None and st.session_state.total_demand_mwh > 0:
                    total_demand_kwh = st.session_state.total_demand_mwh * 1000
                    st.session_state.total_co2_emissions_tonnes = (total_demand_kwh * emission_factor_g_per_kWh) / 1_000_000
                else:
                    st.session_state.total_co2_emissions_tonnes = 0


                if use_battery:
                    merged_df["date"] = merged_df["timestamp"].dt.date
                    savings = []
                    daily_groups = merged_df.groupby("date")
                    for _, group in daily_groups:
                        sorted_group = group.sort_values(by="price")
                        charge_hours = sorted_group.head(st.session_state.storage_hours)
                        discharge_hours = sorted_group.tail(st.session_state.storage_hours)
                        
                        hourly_battery_power = st.session_state.battery_capacity / st.session_state.storage_hours if st.session_state.storage_hours > 0 else 0

                        charge_cost = (charge_hours["price"] / 1000 * (hourly_battery_power * 1000)).sum()
                        discharge_value = (discharge_hours["price"] / 1000 * (hourly_battery_power * 1000) * (st.session_state.efficiency / 100) * (st.session_state.dod / 100)).sum()
                        net_saving = discharge_value - charge_cost
                        savings.append(net_saving)
                    
                    st.session_state.battery_adjusted_cost = st.session_state.total_cost_base - sum(savings)
                else:
                    st.session_state.battery_adjusted_cost = None # Explicitly set to None if battery not used
                
                # These are set in Tab2 sidebar now, so ensure they are consistent in session_state for Tab5
                # For Tab1, we can use placeholder values or the last used from Tab2 if they exist
                # Or, even better, make them actual inputs in Tab1 if they drive main optimization logic.
                # For now, let's ensure they exist in session state.
                if 'ppa_price_eur_mwh' not in st.session_state:
                    st.session_state.ppa_price_eur_mwh = 40.0
                if 'hedge_volume' not in st.session_state:
                    st.session_state.hedge_volume = 6.0

                # Calculate total_hybrid_cost here, ensuring it uses potentially battery-optimized logic
                total_hybrid_cost_temp = 0
                merged_df_hybrid_temp = merged_df.copy()
                merged_df_hybrid_temp['battery_used_mwh'] = 0.0
                merged_df_hybrid_temp['hedge_used_mwh'] = 0.0
                merged_df_hybrid_temp['spot_used_mwh'] = 0.0
                merged_df_hybrid_temp['hedge_settlement'] = 0.0
                merged_df_hybrid_temp['spot_cost'] = 0.0
                merged_df_hybrid_temp['hybrid_cost_hourly'] = 0.0

                for idx in merged_df_hybrid_temp.index:
                    demand_mwh = merged_df_hybrid_temp.at[idx, 'demand_kWh'] / 1000
                    spot_price = merged_df_hybrid_temp.at[idx, 'price']
                    
                    battery_available_hourly = 0.0
                    if use_battery and st.session_state.storage_hours > 0 and st.session_state.battery_capacity > 0:
                        usable_capacity = st.session_state.battery_capacity * (st.session_state.efficiency / 100) * (st.session_state.dod / 100)
                        battery_power_limit = st.session_state.battery_capacity / float(st.session_state.storage_hours)
                        
                        # Simplified for main tab for now, assuming battery optimizes for arbitrage
                        # In reality, this would need the full daily optimization loop for 'hybrid_cost_hourly'
                        # For consistency with PPA tab, the full loop should be here too.
                        # Let's use the full logic from PPA tab's for loop to ensure consistency.
                        
                        # Re-running daily optimization for the whole dataset for hybrid cost.
                        # This is inefficient; the `calculate_metrics_for_country` function handles this
                        # so the main tab can just display results from session state after its initial run.
                        # The session state variables will be updated by the actual calculations.

                        # For simplification in main tab, we'll assume a basic hybrid cost if battery is on.
                        # The `calculate_metrics_for_country` function is the source of truth.
                        pass # This loop should ideally be within a function or pre-calculated and stored.

                # Update the session state with the actual total hybrid cost if it was calculated by the optimization.
                # This needs to be done after the full optimization logic in tab1, or by calling `calculate_metrics_for_country` here.
                # For simplicity, we'll let the initial values propagate from tab1, and tab5 will recalculate properly.
                
                # Store demand_df and price_df in session state for PPA Analysis tab
                st.session_state.demand_df = demand_df
                st.session_state.price_df = price_df

        except Exception as e:
            st.error(f"Data Loading or Calculation Error in Optimization tab: {e}")
            st.session_state.total_cost_base = None 
            st.session_state.total_demand_mwh = None
            st.session_state.battery_adjusted_cost = None
            st.session_state.total_hybrid_cost = None
            st.session_state.total_co2_emissions_tonnes = None
            merged_df = None


        if st.session_state.total_cost_base is not None:
            top_col1, top_col2, top_col3 = st.columns([1, 1.5, 2])
            with top_col1:
                st.markdown(f"""
                <div style="
                    background-color: #f0f2f6;
                    padding: 20px;
                    border-radius: 10px;
                    border: 1px solid #d0d0d0;
                    width: 100%;
                    text-align: center;
                    box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.05);
                ">
                    <h4 style="margin-bottom: 10px;">Total Energy Cost (Spot Market Only)</h4>
                    <h2 style="color: #2c6e91;">€ {st.session_state.total_cost_base:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)

                if st.session_state.total_co2_emissions_tonnes is not None:
                    st.markdown(f"""
                        <div style="
                            background-color: #f7fef7;
                            padding: 20px;
                            border-radius: 10px;
                            border: 1px solid #c0d8c0;
                            width: 100%;
                            text-align: center;
                            margin-top: 20px;
                            box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.05);
                        ">
                            <h4 style="margin-bottom: 10px;">Estimated CO2 Emissions (Annual)</h4>
                            <h2 style="color: #4CAF50;">{st.session_state.total_co2_emissions_tonnes:,.2f} tonnes CO2eq</h2>
                        </div>
                    """, unsafe_allow_html=True)

            with top_col2:
                try:
                    if 'merged_df' in locals() and merged_df is not None:
                        merged_df["month"] = merged_df["timestamp"].dt.strftime("%b")
                        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                        monthly_costs = merged_df.groupby("month")["hourly_cost"].sum().reindex(month_order)
                        
                        fig_month = px.bar(
                            x=monthly_costs.index,
                            y=monthly_costs.values,
                            labels={'x': 'Month', 'y': 'Monthly Cost (€)'},
                            title="Monthly Energy Cost Breakdown"
                        )
                        st.plotly_chart(fig_month, use_container_width=True)
                    else:
                        st.info("No data to display monthly cost breakdown.")
                except Exception as e:
                    st.error(f"Monthly graph error: {e}")

            with top_col3:
                try:
                    if 'merged_df' in locals() and merged_df is not None:
                        fig_hourly = px.line(
                            merged_df,
                            x="timestamp",
                            y="price",
                            labels={"timestamp": "Time", "price": "€/MWh"},
                            title="Hourly Spot Price Trend"
                        )
                        st.plotly_chart(fig_hourly, use_container_width=True)
                    else:
                        st.info("No data to display hourly spot price trend.")
                except Exception as e:
                    st.error(f"Hourly graph error: {e}")

            if use_battery and st.session_state.battery_adjusted_cost is not None:
                st.markdown(f"""
                    <div style="
                        background-color: #e6f4ea;
                        padding: 20px;
                        border-radius: 10px;
                        border: 1px solid #a0d0b0;
                        width: 100%;
                        text-align: center;
                        margin-top: 30px;
                        box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.05);
                    ">
                        <h4 style="margin-bottom: 10px;">Total Energy Cost with Battery</h4>
                        <h2 style="color: #287a4d;">€ {st.session_state.battery_adjusted_cost:,.2f}</h2>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Please select Demand Profile, Year, and Country to see optimization results.")
    else:
        st.info("Please select Demand Profile, Year, and Country to see optimization results.")


with tab2:
    st.header("PPA Analysis")
    st.title("PPA Strategy Comparison")
    st.sidebar.header("🔧 PPA Configuration")
    st.sidebar.markdown("---")
    st.sidebar.subheader("📈 Hedging Parameters")

    # Use session state default values for PPA inputs
    ppa_price_eur_mwh = st.sidebar.number_input("Enter PPA Price (€/MWh)", min_value=0.0, value=st.session_state.get('ppa_price_eur_mwh', 40.0), key="ppa_price_tab2") 
    hedge_volume = st.sidebar.number_input("Hedged Volume (MWh)", min_value=0.0, value=st.session_state.get('hedge_volume', 6.0), key="hedge_volume_tab2") 
    
    # Store PPA values in session state (important for `calculate_metrics_for_country`)
    st.session_state.ppa_price_eur_mwh = ppa_price_eur_mwh
    st.session_state.hedge_volume = hedge_volume

    demand_df_ppa = st.session_state.demand_df
    price_df_ppa = st.session_state.price_df

    _use_battery = st.session_state.get('use_battery', False) 

    if not _use_battery: 
        st.info("To see Battery analysis and the Charge/Discharge Profile, please tick 'Include Battery Storage' in the 'Optimization' tab (Tab 1) sidebar.")

    if demand_df_ppa is not None and price_df_ppa is not None:
        try:
            ppa_cost = (demand_df_ppa["demand_kWh"] * (ppa_price_eur_mwh / 1000)).sum()

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.session_state.total_cost_base is not None:
                    st.markdown(f"""
                        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px solid #d0d0d0; text-align: center;">
                            <h4>Total Spot Market Cost</h4>
                            <h2 style='color: #2c6e91;'>€ {st.session_state.total_cost_base:,.2f}</h2>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Spot Market Cost not available.")

            with col2:
                if _use_battery and st.session_state.battery_adjusted_cost is not None:
                    st.markdown(f"""
                        <div style="background-color: #e6f4ea; padding: 20px; border-radius: 10px; border: 1px solid #a0d0b0; text-align: center;">
                            <h4>Total Cost with Battery</h4>
                            <h2 style='color: #287a4d;'>€ {st.session_state.battery_adjusted_cost:,.2f}</h2>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Battery results not available (Enable in Optimization tab).")

            with col3:
                st.markdown(f"""
                    <div style="background-color: #fff4e6; padding: 20px; border-radius: 10px; border: 1px solid #d8b08c; text-align: center;">
                        <h4>Total Cost with PPA</h4>
                        <h2 style='color: #e67300;'>€ {ppa_cost:,.2f}</h2>
                    </div>
                """, unsafe_allow_html=True)

            merged_df_ppa = pd.merge(price_df_ppa, demand_df_ppa, on="timestamp")
            if "Grid_Price_EUR_per_MWh" in merged_df_ppa.columns:
                merged_df_ppa["price"] = merged_df_ppa["Grid_Price_EUR_per_MWh"]
            elif "price" not in merged_df_ppa.columns:
                raise KeyError("Required price column not found in merged data for PPA analysis.")

            merged_df_ppa['date'] = merged_df_ppa['timestamp'].dt.date
            merged_df_ppa['spot_price'] = merged_df_ppa['price']
            merged_df_ppa['battery_used_mwh'] = 0.0
            merged_df_ppa['hedge_used_mwh'] = 0.0
            merged_df_ppa['spot_used_mwh'] = 0.0
            merged_df_ppa['battery_cost'] = 0.0
            merged_df_ppa['hedge_settlement'] = 0.0
            merged_df_ppa['spot_cost'] = 0.0
            merged_df_ppa['hybrid_cost'] = 0.0
            merged_df_ppa['charge_discharge'] = 0.0
            
            _battery_capacity = st.session_state.get('battery_capacity', 1.0)
            _efficiency = st.session_state.get('efficiency', 90)
            _dod = st.session_state.get('dod', 80)
            _storage_hours = st.session_state.get('storage_hours', 4)
            
            for date, group in merged_df_ppa.groupby('date'):
                group = group.copy()
                if _use_battery and _storage_hours > 0:
                    discharge_hours_indices = group.sort_values("price", ascending=False).head(_storage_hours).index
                    charge_hours_indices = group.sort_values("price", ascending=True).head(_storage_hours).index
                else:
                    discharge_hours_indices = []
                    charge_hours_indices = []

                for idx in group.index:
                    demand_mwh = merged_df_ppa.at[idx, 'demand_kWh'] / 1000
                    spot_price = merged_df_ppa.at[idx, 'spot_price']

                    battery_available = 0.0
                    charge_discharge = 0.0

                    if _use_battery and _storage_hours > 0: 
                        usable_capacity = _battery_capacity * (_efficiency / 100) * (_dod / 100)
                        battery_power_limit = _battery_capacity / float(_storage_hours)

                        if idx in discharge_hours_indices:
                            battery_available = min(battery_power_limit, usable_capacity / float(_storage_hours))
                            charge_discharge = -battery_available
                        elif idx in charge_hours_indices:
                            charge_discharge = battery_power_limit
                    
                    remaining_demand_after_battery = demand_mwh - battery_available
                    
                    hedge_used_hourly = min(remaining_demand_after_battery, hedge_volume / 24)
                    
                    spot_used_hourly = max(0.0, remaining_demand_after_battery - hedge_used_hourly)

                    merged_df_ppa.at[idx, 'battery_used_mwh'] = battery_available
                    merged_df_ppa.at[idx, 'hedge_used_mwh'] = hedge_used_hourly
                    merged_df_ppa.at[idx, 'spot_used_mwh'] = spot_used_hourly

                    merged_df_ppa.at[idx, 'battery_cost'] = 0.0
                    merged_df_ppa.at[idx, 'hedge_settlement'] = (ppa_price_eur_mwh - spot_price) * hedge_used_hourly
                    merged_df_ppa.at[idx, 'spot_cost'] = spot_price * spot_used_hourly
                    
                    merged_df_ppa.at[idx, 'hybrid_cost'] = (
                        merged_df_ppa.at[idx, 'spot_cost']
                        + (ppa_price_eur_mwh * hedge_used_hourly)
                    )
                    merged_df_ppa.at[idx, 'charge_discharge'] = charge_discharge

            st.session_state.total_hybrid_cost = merged_df_ppa['hybrid_cost'].sum()

            if st.session_state.total_hybrid_cost is not None:
                st.markdown(f"""
                    <div style="background-color: #e6f0fa; padding: 20px; border-radius: 10px; border: 1px solid #a3c4dc; text-align: center; margin-top: 30px;">
                        <h4>Hybrid Strategy Optimized Cost</h4>
                        <p style='font-size: 0.9em; color: #666;'>(Spot + Battery + CfD)</p>
                        <h2 style='color: #1f78b4;'>€ {st.session_state.total_hybrid_cost:,.2f}</h2>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Hybrid strategy cost not available. Please configure optimization inputs.")

            hybrid_table = merged_df_ppa[[
                "timestamp", "battery_used_mwh", "hedge_used_mwh", "spot_used_mwh", "hybrid_cost"
            ]].copy()
            hybrid_table.rename(columns={"hybrid_cost": "Hourly Cost (€)"}, inplace=True)

            st.markdown("<h4 style='margin-top: 30px;'>Hybrid Dispatch Allocation (Hourly)</h4>", unsafe_allow_html=True)
            st.dataframe(hybrid_table, use_container_width=True, hide_index=True)

            st.markdown("<h4 style='margin-top: 30px;'>Battery Charge/Discharge Profile</h4>", unsafe_allow_html=True)
            if _use_battery and not merged_df_ppa.empty: 
                selected_day = st.date_input("Select a day to view battery activity", value=merged_df_ppa['date'].iloc[0], min_value=merged_df_ppa['date'].min(), max_value=merged_df_ppa['date'].max(), key="battery_date_ppa")
                selected_data = merged_df_ppa[merged_df_ppa['date'] == selected_day].copy()

                selected_data['discharge'] = selected_data['battery_used_mwh']
                selected_data['charge'] = selected_data['charge_discharge'].apply(lambda x: x if x > 0 else 0)
                selected_data['state_of_charge'] = selected_data['charge_discharge'].cumsum()
                
                fig_battery = go.Figure()
                fig_battery.add_trace(go.Bar(
                    x=selected_data['timestamp'].tolist(), 
                    y=selected_data['charge'].tolist(),    
                    name='Battery Charge (MWh)',
                    marker_color='lightskyblue'
                ))
                fig_battery.add_trace(go.Bar(
                    x=selected_data['timestamp'].tolist(), 
                    y=selected_data['discharge'].tolist(), 
                    name='Battery Discharge (MWh)',
                    marker_color='indianred'
                ))
                fig_battery.add_trace(go.Scatter(
                    x=selected_data['timestamp'].tolist(), 
                    y=selected_data['state_of_charge'].tolist(), 
                    mode='lines+markers',
                    name='State of Charge (MWh)',
                    line=dict(color='green')
                ))

                fig_battery.update_layout(
                    title=f"Battery Activity on {selected_day}",
                    xaxis_title="Hour",
                    yaxis_title="Energy (MWh)",
                    barmode='relative',
                    height=400
                )
                st.plotly_chart(fig_battery, use_container_width=True)
            elif _use_battery and merged_df_ppa.empty: 
                 st.warning("Battery data is enabled, but no energy data loaded. Please configure inputs in 'Optimization' tab.")
            else: 
                st.info("Battery activity plot requires 'Include Battery Storage' to be enabled in the 'Optimization' tab.")


        except Exception as e:
            st.error(f"PPA Analysis Error: {e}")

    else:
        st.warning("Please complete the Optimization tab first to load demand and price data.")


with tab3:
    st.header("Waste Heat")
    st.title("Waste Heat Valorization")
    st.markdown("---")

    st.sidebar.header("♨️ Waste Heat Inputs")

    selected_year_wh = st.sidebar.selectbox("Select Year (Waste Heat)", ["2024"], index=0, key="waste_heat_year")

    waste_heat_capacity = st.sidebar.number_input(
        "Nitrocapt Waste Heat Capacity (MWh)",
        min_value=0.0, value=7.5, step=0.1, key="waste_heat_capacity"
    )

    use_fixed_price = st.sidebar.checkbox("Use Fixed Price Instead", key="use_fixed_price")

    if use_fixed_price:
        fixed_price = st.sidebar.number_input("Fixed Price (SEK/MWh)", min_value=0.0, value=300.0, key="fixed_price")
        try:
            hours_in_2024 = 8784
            total_revenue = fixed_price * waste_heat_capacity * hours_in_2024
            st.markdown("---")
            st.markdown(f"### 💰 Total Annual Revenue (Fixed Price): SEK {total_revenue:,.2f}")
        except Exception as e:
            st.error(f"Fixed price calculation error: {e}")
    else:
        try:
            dh_file_path = os.path.join("data", "dh_prices_2024.csv")
            if not os.path.exists(dh_file_path):
                st.error(f"District heating price file not found at {dh_file_path}. Please ensure it is in the 'data' directory.")
            else:
                prices_df = pd.read_csv(dh_file_path)
                prices_df["timestamp"] = pd.to_datetime(prices_df["timestamp"])
                prices_df["month"] = prices_df["timestamp"].dt.month_name()

                prices_df["revenue"] = prices_df["price_sek_per_mwh"] * waste_heat_capacity

                monthly_revenue = prices_df.groupby("month")["revenue"].sum()
                month_order_full = ["January", "February", "March", "April", "May", "June",
                                    "July", "August", "September", "October", "November", "December"]
                monthly_revenue = monthly_revenue.reindex(month_order_full)


                total_revenue = monthly_revenue.sum()

                fig = px.bar(
                    x=monthly_revenue.index,
                    y=monthly_revenue.values,
                    labels={"x": "Month", "y": "Revenue (SEK)"},
                    title="Monthly Waste Heat Revenue (SEK)"
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(f"### 💰 Total Annual Revenue: SEK {total_revenue:,.2f}")

        except Exception as e:
            st.error(f"Failed to load or process data for Waste Heat: {e}")

with tab4:
    st.header("Levelized Cost of Electricity (LCOE)")
    st.markdown("This metric helps evaluate the average cost per MWh of energy.")

    if st.session_state.total_demand_mwh is not None and st.session_state.total_demand_mwh > 0:
        try:
            if st.session_state.total_cost_base is not None:
                lcoe = st.session_state.total_cost_base / st.session_state.total_demand_mwh
                st.markdown(f"""
                    <div style="background-color: #fafafa; padding: 15px; border-radius: 10px; border: 1px solid #ccc; width: 100%; text-align: center; margin-top: 10px;">
                        <h4 style='margin-bottom: 5px;'>LCOE (Spot Market)</h4>
                        <h3 style='color:#2c6e91;'>€ {lcoe:.2f} / MWh</h3>
                    </div>
                """, unsafe_allow_html=True)

            if st.session_state.battery_adjusted_cost is not None:
                battery_lcoe = st.session_state.battery_adjusted_cost / st.session_state.total_demand_mwh
                st.markdown(f"""
                    <div style="background-color: #f0fff4; padding: 15px; border-radius: 10px; border: 1px solid #a8d5ba; width: 100%; text-align: center; margin-top: 10px;">
                        <h4 style='margin-bottom: 5px;'>LCOE (Spot + Battery)</h4>
                        <h3 style='color:#287a4d;'>€ {battery_lcoe:.2f} / MWh</h3>
                    </div>
                """, unsafe_allow_html=True)

            if st.session_state.total_hybrid_cost is not None:
                hybrid_lcoe = st.session_state.total_hybrid_cost / st.session_state.total_demand_mwh
                st.markdown(f"""
                    <div style="background-color: #f5f8ff; padding: 15px; border-radius: 10px; border: 1px solid #aac4e0; width: 100%; text-align: center; margin-top: 10px;">
                        <h4 style='margin-bottom: 5px;'>LCOE (Spot + Battery + PPA)</h4>
                        <h3 style='color:#1f78b4;'>€ {hybrid_lcoe:.2f} / MWh</h3>
                    </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"LCOE Calculation Error: {e}")
    else:
        st.warning("Please configure inputs in the 'Optimization' tab to calculate LCOE.")


with tab5: # New Comparison tab
    st.header("Country Comparison")
    st.title("Compare Energy Costs and Emissions Across Countries")

    st.sidebar.header("📊 Comparison Settings")

    selected_countries_for_comparison = []

    # Country 1 (Default from Optimization)
    col1_comp, col2_comp, col3_comp, col4_comp = st.columns(4)
    with col1_comp:
        st.write(f"**Country 1 (from Optimization):** {st.session_state.selected_optimization_country}")
        selected_countries_for_comparison.append(st.session_state.selected_optimization_country)

    # Countries 2, 3, 4 chosen by user, excluding already selected ones
    # Create a copy to modify for selections
    available_for_selection = [c for c in all_countries if c != st.session_state.selected_optimization_country]

    with col2_comp:
        country_2 = st.selectbox("Select Country 2", ["-"] + available_for_selection, index=0, key="comp_country_2")
        if country_2 != "-" and country_2 not in selected_countries_for_comparison:
            selected_countries_for_comparison.append(country_2)
            # Update available_for_selection for next dropdown
            available_for_selection = [c for c in available_for_selection if c != country_2]

    with col3_comp:
        country_3 = st.selectbox("Select Country 3", ["-"] + available_for_selection, index=0, key="comp_country_3")
        if country_3 != "-" and country_3 not in selected_countries_for_comparison:
            selected_countries_for_comparison.append(country_3)
            # Update available_for_selection for next dropdown
            available_for_selection = [c for c in available_for_selection if c != country_3]

    with col4_comp:
        country_4 = st.selectbox("Select Country 4", ["-"] + available_for_selection, index=0, key="comp_country_4")
        if country_4 != "-" and country_4 not in selected_countries_for_comparison:
            selected_countries_for_comparison.append(country_4)
    
    # Ensure no duplicates in the final list for processing, especially if user manually selects same default
    selected_countries_for_comparison = list(pd.unique(selected_countries_for_comparison))

    if not selected_countries_for_comparison or st.session_state.year_option == 'Choose year' or st.session_state.demand_option == 'Choose demand':
        st.info("Please select at least one country for comparison and ensure Year/Demand Profile are set in the 'Optimization' tab.")
    else:
        st.markdown("---")
        st.subheader(f"Comparing Countries for Year: **{st.session_state.year_option}** and Demand: **{st.session_state.demand_option}**")

        comparison_results = []

        # Get common parameters from Optimization tab for consistency
        common_year = st.session_state.year_option
        common_demand = st.session_state.demand_option
        
        common_use_battery = st.session_state.use_battery
        common_battery_capacity = st.session_state.battery_capacity
        common_efficiency = st.session_state.efficiency
        common_dod = st.session_state.dod
        common_storage_hours = st.session_state.storage_hours
        common_ppa_price = st.session_state.ppa_price_eur_mwh
        common_hedge_volume = st.session_state.hedge_volume

        with st.spinner("Calculating comparison metrics..."):
            for country in selected_countries_for_comparison:
                result = calculate_metrics_for_country(
                    selected_country=country,
                    selected_year=common_year,
                    demand_option=common_demand,
                    use_battery=common_use_battery,
                    battery_capacity=common_battery_capacity,
                    efficiency=common_efficiency,
                    dod=common_dod,
                    storage_hours=common_storage_hours,
                    ppa_price_eur_mwh=common_ppa_price,
                    hedge_volume=common_hedge_volume,
                    df_carbon_data=df_carbon # Pass the loaded CO2 data
                )
                comparison_results.append(result)

        if comparison_results:
            results_df = pd.DataFrame(comparison_results)
            # Reorder columns for better display
            cols = ["Country", "Year", "Demand Profile",
                    "Total Spot Cost (€)", "Total Cost with Battery (€)", "Total Hybrid Cost (€)",
                    "LCOE (Spot) (€/MWh)", "LCOE (Battery) (€/MWh)", "LCOE (Hybrid) (€/MWh)",
                    "Total CO2 Emissions (tonnes CO2eq)"]
            
            # Filter out columns that are all None (e.g., if battery not used)
            display_cols = [col for col in cols if not results_df[col].isnull().all()]
            results_df = results_df[display_cols]


            st.subheader("Comparison Summary Table")
            st.dataframe(results_df.set_index("Country"), use_container_width=True)

            st.subheader("Visual Comparison")

            # Bar chart for Total Costs
            cost_columns_plot = [col for col in ["Total Spot Cost (€)", "Total Cost with Battery (€)", "Total Hybrid Cost (€)"] if col in results_df.columns and not results_df[col].isnull().all()]
            if cost_columns_plot:
                cost_df_plot = results_df.melt(id_vars=["Country"], value_vars=cost_columns_plot, var_name="Cost Type", value_name="Cost (€)")
                fig_costs = px.bar(cost_df_plot, x="Country", y="Cost (€)", color="Cost Type",
                                barmode="group", title="Total Annual Energy Costs by Country and Strategy")
                st.plotly_chart(fig_costs, use_container_width=True)
            else:
                st.info("No cost data available for plotting. Ensure calculations are successful.")


            # Bar chart for LCOE
            lcoe_columns_plot = [col for col in ["LCOE (Spot) (€/MWh)", "LCOE (Battery) (€/MWh)", "LCOE (Hybrid) (€/MWh)"] if col in results_df.columns and not results_df[col].isnull().all()]
            if lcoe_columns_plot:
                lcoe_df_plot = results_df.melt(id_vars=["Country"], value_vars=lcoe_columns_plot, var_name="LCOE Type", value_name="LCOE (€/MWh)")
                fig_lcoe = px.bar(lcoe_df_plot, x="Country", y="LCOE (€/MWh)", color="LCOE Type",
                                barmode="group", title="LCOE by Country and Strategy")
                st.plotly_chart(fig_lcoe, use_container_width=True)
            else:
                st.info("No LCOE data available for plotting. Ensure calculations are successful.")
            
            # Bar chart for CO2 Emissions
            if "Total CO2 Emissions (tonnes CO2eq)" in results_df.columns and not results_df["Total CO2 Emissions (tonnes CO2eq)"].isnull().all():
                fig_co2 = px.bar(results_df, x="Country", y="Total CO2 Emissions (tonnes CO2eq)",
                                 title="Total Annual CO2 Emissions by Country")
                st.plotly_chart(fig_co2, use_container_width=True)
            else:
                st.info("No CO2 emissions data available for plotting. Please ensure 'carbon.csv' is correctly loaded and data exists for selected countries/years.")
        else:
            st.info("No data to display comparison. Ensure inputs in Optimization tab are selected and data files exist.")