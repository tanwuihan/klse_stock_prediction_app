import pandas as pd
from datetime import datetime

REQUIRED_COLUMNS = {"Date", "High", "Low", "Close", "Open", "Volume"}

def get_klse_tickers(excel_path):
    df = pd.read_excel(excel_path, engine="openpyxl").iloc[1:]
    df.columns = ["Company", "Stock Code"]
    df["Stock Code"] = df["Stock Code"].astype(str).str.zfill(4) + ".KL"
    df["Display"] = df["Company"] + " (" + df["Stock Code"] + ")"
    return df

def filter_spiking_stocks(stock_data, threshold):
    selected = {}
    for ticker, df in stock_data.items():
        try:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.sort_values("Date")  # Ensure chronological order

            # Ensure numeric columns
            df["High"] = pd.to_numeric(df["High"], errors="coerce")
            df["Low"] = pd.to_numeric(df["Low"], errors="coerce")

            latest = df.dropna(subset=["High", "Low"]).iloc[-1]
            spike = latest["High"] - latest["Low"]

            if spike > threshold:
                selected[ticker] = df
        except Exception as e:
            print(f"❌ Error processing {ticker}: {e}")
    return selected
