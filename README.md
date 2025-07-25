# Energy-optimization
Streamlit dashboard for industrial energy optimization using spot prices, PPA, and battery simulation

# ⚡ Energy Optimization App

**Web App:** [energy‑opt.streamlit.app](https://energy-opt.streamlit.app)  
**Built with:** Python • Streamlit • Pandas • Plotly (and optionally PVGIS API)


## 🚀 Overview

This app helps users simulate and optimize energy systems that may include:

- Spot market
- Battery energy storage  
- PPA 
- Waste-heat recovery  

The simulation models system energy balance, supports peak shaving, and provides recommendations for cost-efficient system configurations.


## 📦 Features

- Upload consumption CSV data (quarter-hour timestamps, power in kW)
- Generate production profiles via PVGIS (or input alternate data)
- Simulate battery behavior, spot market , PPA hybrid and waste heat monetization
- Perform peak shaving and monitor grid price data (e.g. Czech market)
- View interactive graphs and tables  
- Export results and summary report as a PDF  

