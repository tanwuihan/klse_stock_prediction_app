import streamlit as st
import pandas as pd
import re
from firebase_admin import firestore
from google.cloud.firestore import Query
from firebase_auth import ensure_login, logout_user
from datetime import datetime

# === Login Check ===
if not ensure_login():
    st.warning("Please login to access this page.")
    st.stop()

st.set_page_config(page_title="📜 Prediction History", layout="wide")

# === Sidebar ===
st.sidebar.write(f"👋 Logged in as: {st.session_state.get('email', 'Unknown')}")
if st.sidebar.button("🚪 Logout"):
    logout_user()

st.title("📜 Your Prediction History")

# === Firestore Client ===
db = firestore.client()
user_email = st.session_state.get("email")

# === Fetch Prediction History ===
def get_user_predictions(email):
    docs = db.collection("predictions").document(email).collection("history").order_by(
        "timestamp", direction=Query.DESCENDING
    ).stream()
    history = []
    for doc in docs:
        history.append(doc.to_dict())
    return history

history_data = get_user_predictions(user_email)

if not history_data:
    st.info("You have no past predictions yet.")
    st.stop()

# === Convert to DataFrame ===
df = pd.DataFrame(history_data)

# Format timestamp column
if "timestamp" in df.columns:
    df["timestamp"] = df["timestamp"].apply(
        lambda x: x.strftime("%Y-%m-%d %H:%M") if isinstance(x, datetime) else str(x)
    )

# Keep stock as "Stock Name (Stock Code)"
if "stock" in df.columns:
    df["stock"] = df["stock"].apply(
        lambda s: re.search(r"^(.*?)\s\((.*?)\)", s).group(0) if isinstance(s, str) and "(" in s else s
    )

# Rename columns only if they exist
rename_map = {
    "timestamp": "Timestamp",
    "stock": "Stock",
    "model": "Model",
    "period": "Period",
    "latest_price": "Latest Price",
    "predicted_price": "Predicted Price",
    "suggestion": "Suggestion"
}
df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

# Keep only existing columns in correct order
display_cols = [v for v in rename_map.values() if v in df.columns]
df_main = df[display_cols]

# === Display main table ===
st.dataframe(df_main, hide_index=True)

# === Filter by Stock ===
st.subheader("🔍 Filter by Stock")
if "Stock" in df_main.columns:
    stock_list = df_main["Stock"].unique().tolist()
    selected_stock = st.selectbox("Select Stock", stock_list)

    filtered_df = df_main[df_main["Stock"] == selected_stock]
    st.dataframe(filtered_df, hide_index=True)
