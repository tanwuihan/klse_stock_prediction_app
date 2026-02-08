import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import base64
import requests
import io
import random
import sys

# ================= CONFIG =================
EXCEL_PATH = "List_of_Companies.xlsx"
EXPECTED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

MAX_RETRIES = 3
BASE_DELAY = 2
COOL_DOWN = 90

# GitHub Repo Info
GITHUB_USER = "tanwuihan"
REPO_NAME = "klse-prediction"
BRANCH = "main"
TOKEN = "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"

FOLDER_PATH = "stock_data"

RAW_API = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents"
RAW_GITHUB = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

DELISTED_FILE = "delisted_log.txt"
# ==========================================


def load_delisted_tickers():
    if not os.path.exists(DELISTED_FILE):
        return set()
    with open(DELISTED_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())


def save_delisted_ticker(ticker):
    with open(DELISTED_FILE, "a") as f:
        f.write(f"{ticker}\n")


def get_klse_tickers(path):
    df = pd.read_excel(path, engine="openpyxl").iloc[1:]
    df.columns = ["Company", "Stock Code"]
    df["Stock Code"] = df["Stock Code"].astype(str).str.zfill(4) + ".KL"
    return df["Stock Code"].tolist()


def upload_to_github(ticker, df):
    """Upload CSV to GitHub (overwrite existing)."""
    csv_buffer = io.StringIO()
    df = df.reset_index(drop=True)
    if "Date" not in df.columns:
        df.rename(columns={df.columns[0]: "Date"}, inplace=True)
    df[["Date"] + EXPECTED_COLUMNS].to_csv(csv_buffer, index=False)
    content = base64.b64encode(csv_buffer.getvalue().encode()).decode()

    filename = f"{ticker}.csv"
    url = f"{RAW_API}/{FOLDER_PATH}/{filename}"

    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json()["sha"]
        data = {"message": f"Update {filename}", "content": content, "branch": BRANCH, "sha": sha}
    else:
        print(f"⚠️ {ticker} file missing in GitHub. Skipping upload.")
        return False

    r = requests.put(url, headers=headers, json=data)
    if r.status_code in (200, 201):
        commit_sha = r.json().get("commit", {}).get("sha")
        print(f"✅ Uploaded: {filename} (Commit: {commit_sha})")
        return True
    else:
        print(f"❌ GitHub Upload Failed for {filename}: {r.status_code} - {r.text}")
        return False


def handle_rate_limit(error_message):
    if "Too Many Requests" in error_message or "Rate limited" in error_message:
        print(f"⏳ Rate limit hit — cooling down for {COOL_DOWN} seconds...")
        time.sleep(COOL_DOWN)
        return True
    return False


def fetch_incremental(ticker, last_date):
    """Download only new rows since last_date using Ticker.history()."""
    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.today().strftime("%Y-%m-%d")
    if start_date >= today:
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=today, interval="1d", actions=False)

            if not df.empty:
                df.reset_index(inplace=True)
                # normalize timezone → naive
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
                return df
            return None
        except Exception as e:
            if handle_rate_limit(str(e)):
                continue
            print(f"❌ Error fetching {ticker}: {e}")
        time.sleep(BASE_DELAY * attempt + random.uniform(0.5, 1.5))
    return None


def update_ticker(ticker):
    """Update CSV for an existing ticker in GitHub."""
    url = f"{RAW_GITHUB}/{FOLDER_PATH}/{ticker}.csv"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"⚠️ {ticker} has no file in GitHub. Skipping.")
        return

    existing_df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"])
    if existing_df.empty:
        print(f"❌ {ticker} file exists but no data. Marking as delisted.")
        save_delisted_ticker(ticker)
        return

    # normalize timezone → naive
    existing_df["Date"] = pd.to_datetime(existing_df["Date"]).dt.tz_localize(None)

    last_date = existing_df["Date"].max().date()

    new_df = fetch_incremental(ticker, last_date)
    if new_df is not None and not new_df.empty:
        combined_df = pd.concat([existing_df, new_df])
        combined_df.drop_duplicates(subset=["Date"], inplace=True)
        combined_df.sort_values("Date", inplace=True)

        max_date = combined_df["Date"].max().date()
        if max_date > last_date:
            if upload_to_github(ticker, combined_df):
                print(f"🔄 Updated {ticker} with {len(new_df)} new rows. Last date now {max_date}")
        else:
            print(f"⚠️ {ticker}: No truly new rows beyond {last_date}.")
    else:
        print(f"⚠️ {ticker}: No newer data available on Yahoo. Last date remains {last_date}")


def main():
    all_tickers = get_klse_tickers(EXCEL_PATH)
    print(f"🔽 Total tickers to process: {len(all_tickers)}")

    failed = []
    for ticker in all_tickers:
        try:
            update_ticker(ticker)
        except Exception as e:
            print(f"❌ Error with {ticker}: {e}")
            failed.append(ticker)
        time.sleep(random.uniform(1, 3))

    print(f"\n✅ Finished. Failed tickers: {len(failed)}")
    if failed:
        with open("failed_run.txt", "w") as f:
            for t in failed:
                f.write(t + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Script stopped by user.")
        sys.exit(0)
