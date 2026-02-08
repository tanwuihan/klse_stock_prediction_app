import streamlit as st
import pandas as pd
import requests
import os
import altair as alt
from datetime import datetime
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from modules.data_utils import get_klse_tickers, filter_spiking_stocks
from firebase_auth import ensure_login, logout_user
import hashlib
import io

# === Load Environment Variables ===
load_dotenv()

st.set_page_config(page_title="📊 Dashboard", layout="wide")

# === Login Check ===
if not ensure_login():
    st.warning("Please login to access this page.")
    st.stop()

st.sidebar.write(f"👋 Logged in as: {st.session_state.get('email', 'Unknown')}")
if st.sidebar.button("🚪 Logout"):
    logout_user()

st.title("📈 KLSE Dashboard")

# === Load stock data from GitHub ===
@st.cache_data(ttl=86400, show_spinner="📥 Loading stock data from GitHub...")
def load_today_stock_data():
    base_url = "https://raw.githubusercontent.com/tanwuihan/klse-prediction/main/stock_data"
    ticker_df = get_klse_tickers("List_of_Companies.xlsx")
    tickers = ticker_df["Stock Code"].tolist()

    stock_data = {}
    for ticker in tickers:
        url = f"{base_url}/{ticker}.csv"  # ✅ No more date folder
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                df.columns = [c.strip().capitalize() for c in df.columns]
                if {"Date", "High", "Low"}.issubset(df.columns):
                    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
                    df = df.dropna(subset=["Date", "High", "Low"])
                    stock_data[ticker] = df
        except Exception:
            continue
    return stock_data, ticker_df

stock_data, ticker_df = load_today_stock_data()
display_map = dict(zip(ticker_df["Stock Code"], ticker_df["Company"]))

# === Top 10 Spiking Stocks ===
st.subheader("🚀 Top 10 Most Spiking Stocks Today")
spiked = filter_spiking_stocks(stock_data, threshold=0)
spike_list = []
for ticker, df in spiked.items():
    latest = df.sort_values("Date").iloc[-1]
    spike_amt = latest["High"] - latest["Low"]
    spike_list.append((ticker, spike_amt))

top_spikes = sorted(spike_list, key=lambda x: x[1], reverse=True)[:10]
display_names = [f"{display_map.get(ticker, ticker)} ({ticker})" for ticker, _ in top_spikes]
clean_df = pd.DataFrame({
    "Stock": display_names,
    "Price Spike (MYR)": [spike for _, spike in top_spikes]
})

if clean_df.empty:
    st.warning("No spike data found.")
else:
    chart = alt.Chart(clean_df).mark_bar().encode(
        x=alt.X('Price Spike (MYR):Q', title='Price Spike (MYR)'),
        y=alt.Y('Stock:N', sort='-x', title=None),
        tooltip=['Stock', 'Price Spike (MYR)']
    ).properties(width=600, height=400, title='Top 10 Spiking Stocks')
    st.altair_chart(chart, use_container_width=True)

# === Financial Report Summary ===
st.subheader("📄 Financial Report Summary")

st.markdown("""
📘 *Tutorial: How to get a company's financial report from Bursa Malaysia*
1. Visit [Bursa Malaysia Company Announcements](https://www.bursamalaysia.com/market_information/announcements/company_announcement).
2. Search for your company by name or stock code.
3. Filter by *Financial Announcements (FA)*.
4. Download the *latest Quarterly Report (QR)* or *Annual Report (AR)* in PDF.

⬇️ Once downloaded, upload the PDF file below and I will summarize it for you.
""")

uploaded_pdf = st.file_uploader("📤 Upload Financial Report (PDF)", type=["pdf"], key="financial_pdf")

def extract_text_from_bytes(data: bytes):
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception:
        return None

# === Ollama Summarizer ===
def summarize_with_ollama(prompt, model="mistral"):
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=360
        )
        if res.status_code == 200:
            return res.json().get("response", "").strip()
        else:
            return f"❌ Error: {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Ollama connection error: {e}"

# === Cache busting based on file content ===
# If the user clears the uploader, also clear cached summary
if uploaded_pdf is None:
    st.session_state.pop("financial_summary", None)
    st.session_state.pop("financial_file_hash", None)
else:
    # Compute a stable hash of the current uploaded file
    file_bytes = uploaded_pdf.getvalue()
    curr_hash = hashlib.sha256(file_bytes).hexdigest()

    # Only summarize when the hash changes (new/different file)
    if st.session_state.get("financial_file_hash") != curr_hash:
        with st.spinner("📥 Reading financial report..."):
            text = extract_text_from_bytes(file_bytes)

        if text:
            prompt = f"""
You are an equity analyst. Analyse this company's financial report.
Scan both text AND tables to extract the most recent full year data.

[KPIs to extract if possible]
- Revenue
- Profit for the Year

Rules:
- Do not leave values as N/A if they clearly exist in financial tables.
- Approximate if numbers are obvious.
- If Share Price is missing, tell the user it’s required for P/E and dividend yield.

[Output sections exactly]
1) Snapshot – 3 concise bullets (growth, profitability, leverage).
2) Key Metrics – bullet list of above KPIs with numbers.
3) Outlook & Catalysts – 3–5 bullets.
4) Risks – 3 bullets.
5) Valuation & Strategy – choose [Accumulate, Hold for income, Neutral/Watchlist, Avoid] with rationale.

Keep it under 280 words, clear and actionable.

Here is the report text:
{text[:8000]}
"""
            with st.spinner("🧠 Summarizing with Ollama..."):
                summary = summarize_with_ollama(prompt)
        else:
            summary = "⚠️ Failed to extract text from PDF."

        st.session_state["financial_summary"] = summary
        st.session_state["financial_file_hash"] = curr_hash

# Show summary if available
if st.session_state.get("financial_summary"):
    st.markdown("### 🧾 Financial Summary")
    st.markdown(st.session_state["financial_summary"])

    cols = st.columns(2)
    with cols[0]:
        if st.button("🔁 Re-summarize this file (force)"):
            # Force a refresh by deleting the stored hash
            st.session_state.pop("financial_file_hash", None)
            st.rerun()
    with cols[1]:
        if st.button("🧹 Clear summary"):
            st.session_state.pop("financial_summary", None)
            st.session_state.pop("financial_file_hash", None)
            st.rerun()

# === FAQ Chatbot Section (Below Financial Report Summary) ===
st.subheader("🤖 FAQ Chatbot")

st.write("👋 Hi! I’m your KLSE Assistant. What would you like to know?")

faq_question = st.selectbox(
    "Choose a question:",
    [
        "What is this system about?",
        "How to use this system?",
        "Give me financial advice for a stock"
    ],
    key="faq_dropdown_section"
)

if faq_question == "Give me financial advice for a stock":
    stock_selected = st.selectbox(
        "Choose a stock:",
        list(display_map.keys()),
        format_func=lambda x: f"{display_map.get(x, x)} ({x})",
        key="faq_stock_section"
    )

    if st.button("Ask Ollama for Advice", key="ask_advice_section"):
        prompt = f"Please give financial advice for {display_map.get(stock_selected, stock_selected)} ({stock_selected}) based on its historical performance, KLSE market trends, and possible future outlook."
        with st.spinner("💬 Ollama is thinking..."):
            answer = summarize_with_ollama(prompt)

        if "❌" in answer:
            st.error(answer)
        else:
            st.success("✅ Answer:")
            st.markdown(answer)

else:
    if st.button("Ask FAQ Bot", key="ask_faq_section"):
        answers = {
            "What is this system about?": "This KLSE Stock Prediction System forecasts Malaysian stock prices using AI models (Prophet, XGBoost, LSTM). It also shows the most volatile stocks and summarizes the latest financial reports.",
            "How to use this system?": "Use the sidebar to access features. View prediction charts, spike stocks, and summaries. Choose stocks to explore further."
        }
        st.success("✅ Answer:")
        st.markdown(answers[faq_question])
