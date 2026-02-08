import streamlit as st
import numpy as np
import pandas as pd
import altair as alt
from datetime import datetime
import requests
import io
import uuid  # ✅ For unique Firestore document IDs

from firebase_config import db  # Firestore client
from modules.data_utils import get_klse_tickers, filter_spiking_stocks
from modules.prediction_models import predict_prophet, predict_xgboost, predict_lstm
from firebase_auth import ensure_login, logout_user

st.set_page_config(page_title="Predict Stock", layout="wide")

# Tooltip styling
TOOLTIP_STYLE = """
<style>
.tooltip {
  position: relative;
  display: inline-block;
  cursor: help;
  color: #6c757d;
  font-weight: bold;
}
.tooltip .tooltiptext {
  visibility: hidden;
  width: 230px;
  background-color: #333;
  color: #fff;
  text-align: left;
  border-radius: 6px;
  padding: 8px;
  position: absolute;
  z-index: 1;
  bottom: 125%;
  left: 50%;
  margin-left: -115px;
  opacity: 0;
  transition: opacity 0.3s;
  font-size: 12px;
}
.tooltip:hover .tooltiptext {
  visibility: visible;
  opacity: 1;
}
</style>
"""
st.markdown(TOOLTIP_STYLE, unsafe_allow_html=True)

def tooltip_label(label, tip):
    return f'{label} <span class="tooltip">ⓘ<span class="tooltiptext">{tip}</span></span>'

# === Login Check ===
if not ensure_login():
    st.warning("Please login to access this page.")
    st.stop()

# Sidebar
st.sidebar.write(f"👋 Logged in as: {st.session_state.get('email', 'Unknown')}")
if st.sidebar.button("🚪 Logout"):
    logout_user()

st.title("🔮 Stock Prediction")

# --- User Inputs ---
st.markdown(tooltip_label("**Select Historical Period**", "Choose how many years of past stock data to use for prediction."), unsafe_allow_html=True)
period = st.radio("", ["5y", "10y"], label_visibility="collapsed")

st.markdown(tooltip_label("**Spike Threshold (MYR)**", "How much price spike on today."), unsafe_allow_html=True)
threshold = st.slider("", 0.01, 2.00, 0.50, label_visibility="collapsed")

st.markdown(tooltip_label("**Days to Predict**", "How many future trading days to forecast."), unsafe_allow_html=True)
future_days = st.slider("", 1, 30, 5, label_visibility="collapsed")

# --- Load tickers ---
ticker_df = get_klse_tickers("List_of_Companies.xlsx")
tickers = ticker_df["Stock Code"].tolist()
display_map = dict(zip(ticker_df["Stock Code"], ticker_df["Display"]))

# --- GitHub Config ---
BASE_RAW_URL = "https://raw.githubusercontent.com/tanwuihan/klse-prediction/main/stock_data"

@st.cache_data(show_spinner="📥 Downloading stock data from GitHub...")
def load_github_csv(ticker):
    url = f"{BASE_RAW_URL}/{ticker}.csv"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        print(f"❌ Error loading {ticker}: {e}")
    return None

# Load stock data (always latest CSV per ticker)
stock_data = {}
for ticker in tickers:
    df = load_github_csv(ticker)
    if df is not None and not df.empty:
        stock_data[ticker] = df

if not stock_data:
    st.error("No stock data loaded from GitHub. Please check if the CSV files exist.")
    st.stop()

# Filter spiking stocks
filtered = filter_spiking_stocks(stock_data, threshold)
if not filtered:
    st.warning("No stocks with spike above threshold.")
    st.stop()

# Stock selection
dropdown_options = {display_map[t]: t for t in filtered}
selected_label = st.selectbox("Select Stock", list(dropdown_options.keys()))
selected_ticker = dropdown_options[selected_label]
df = filtered[selected_ticker]

# Historical Chart
st.markdown("📉 **Historical Stock Price Chart**")
chart1 = alt.Chart(df).mark_line(color='steelblue').encode(
    x='Date:T',
    y='Close:Q'
).properties(height=300)
st.altair_chart(chart1, use_container_width=True)

# Predictions
res_p, hist_p, mape_p = predict_prophet(df.copy(), period, future_days)
res_x, hist_x, mape_x = predict_xgboost(df.copy(), period, future_days)
res_l, hist_l, mape_l = predict_lstm(df.copy(), period, future_days)

acc_p = 100 - mape_p if mape_p is not None else None
acc_x = 100 - mape_x if mape_x is not None else None
acc_l = 100 - mape_l if mape_l is not None else None

accuracies = {"Prophet": acc_p, "XGBoost": acc_x, "LSTM": acc_l}
recommended_model = min(accuracies, key=lambda k: 100 - accuracies[k] if accuracies[k] is not None else float('inf'))

# Accuracy display
st.markdown("### 📈 Prediction Accuracy:")
st.markdown(f"- Prophet: {acc_p:.2f}%" if acc_p else "- Prophet: N/A")
st.markdown(f"- XGBoost: {acc_x:.2f}%" if acc_x else "- XGBoost: N/A")
st.markdown(f"- LSTM: {acc_l:.2f}%" if acc_l else "- LSTM: N/A")
st.success(f"✅ Recommended Model: **{recommended_model}**")

# Model choice
model_choice = st.selectbox("Choose a model", ["Prophet", "XGBoost", "LSTM"], index=["Prophet", "XGBoost", "LSTM"].index(recommended_model))
selected_result, selected_hist = {
    "Prophet": (res_p, hist_p),
    "XGBoost": (res_x, hist_x),
    "LSTM": (res_l, hist_l)
}[model_choice]

# Show predictions
if selected_result is not None:
    st.subheader(f"🔮 Predicted Prices for next {future_days} day(s) - {model_choice}")
    st.dataframe(selected_result)

    # Chart comparison
    actual_30 = df[["Date", "Close"]].dropna().tail(30)
    predicted_30 = selected_hist[-30:] if selected_hist is not None else pd.DataFrame(columns=["Date", "Predicted Price"])
    comparison_df = pd.DataFrame({
        "Date": actual_30["Date"].values,
        "Actual Price": actual_30["Close"].values,
        "Predicted Price": predicted_30["Predicted Price"].values if not predicted_30.empty else [np.nan] * len(actual_30)
    })

    chart2 = alt.Chart(comparison_df).transform_fold(
        ["Actual Price", "Predicted Price"], as_=["Type", "Value"]
    ).mark_line().encode(x='Date:T', y='Value:Q', color='Type:N').properties(height=300)
    st.altair_chart(chart2, use_container_width=True)

    # Investment Suggestion
    pred_prices = pd.to_numeric(selected_result["Predicted Price"], errors='coerce').dropna()
    close_prices = pd.to_numeric(df["Close"], errors='coerce').dropna()
    if not pred_prices.empty and not close_prices.empty:
        avg_pred_price = pred_prices.mean()
        latest_price = close_prices.iloc[-1]
        change_pct = (avg_pred_price - latest_price) / latest_price * 100

        if change_pct > 2:
            suggestion = "💹 **Buy** - Price expected to rise."
        elif change_pct < -2:
            suggestion = "📉 **Sell** - Price expected to drop."
        else:
            suggestion = "🤝 **Hold** - No major change expected."

        st.subheader("📢 Investment Suggestion")
        st.markdown(f"**Latest Price:** RM {latest_price:.2f}")
        st.markdown(f"**Avg Predicted Price:** RM {avg_pred_price:.2f} ({change_pct:.2f}%)")
        st.success(suggestion)

        # ✅ Save to Firestore with unique ID
        doc_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}"
        db.collection("predictions").document(st.session_state.get("email")).collection("history").document(doc_id).set({
            "timestamp": datetime.now(),
            "stock": f"{display_map[selected_ticker]} ({selected_ticker})",
            "model": model_choice,
            "period": period,
            "latest_price": float(latest_price),
            "predicted_price": float(avg_pred_price),
            "suggestion": suggestion
        })
