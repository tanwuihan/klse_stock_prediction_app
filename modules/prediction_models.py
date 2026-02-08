import pandas as pd
import numpy as np
import tensorflow as tf
from prophet import Prophet
from xgboost import XGBRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error


# === Prophet Model ===
def predict_prophet(df, years, future_days):
    df = df[["Date", "Close"]].dropna()
    df.columns = ["ds", "y"]
    df["ds"] = pd.to_datetime(df["ds"])

    end_date = df["ds"].max()
    start_date = end_date - pd.DateOffset(years=int(years.replace("y", "")))
    df = df[df["ds"] >= start_date]

    model = Prophet(daily_seasonality=False)
    model.fit(df)

    # Future prediction
    future = model.make_future_dataframe(periods=future_days)
    forecast = model.predict(future)
    prediction = forecast[["ds", "yhat"]].tail(future_days)
    prediction.columns = ["Date", "Predicted Price"]

    # Historical prediction (for MAPE)
    forecast_hist = forecast[["ds", "yhat"]]
    forecast_hist = forecast_hist[forecast_hist["ds"] <= df["ds"].max()]
    merged = pd.merge(df, forecast_hist, on="ds", how="inner")
    merged.dropna(inplace=True)
    mape = mean_absolute_percentage_error(merged["y"], merged["yhat"]) * 100 if not merged.empty else None

    hist_pred = pd.DataFrame({"Date": merged["ds"], "Predicted Price": merged["yhat"]})
    return prediction, hist_pred, round(mape, 2) if mape is not None else None


# === XGBoost Model ===
def predict_xgboost(df, years, future_days):
    df = df[["Date", "Close"]].dropna()
    df["Date"] = pd.to_datetime(df["Date"])

    end_date = df["Date"].max()
    start_date = end_date - pd.DateOffset(years=int(years.replace("y", "")))
    df = df[df["Date"] >= start_date].copy()

    df["Target"] = df["Close"].shift(-1)
    df.dropna(inplace=True)

    df["Index"] = np.arange(len(df))
    X = df[["Index"]]
    y = df["Target"]

    model = XGBRegressor()
    model.fit(X, y)

    # Predict historical (for MAPE)
    preds_hist = model.predict(X)
    mape = mean_absolute_percentage_error(y, preds_hist) * 100 if len(y) == len(preds_hist) else None

    hist_pred = pd.DataFrame({"Date": df["Date"], "Predicted Price": preds_hist})

    # Predict future
    last_index = df["Index"].max()
    future_indices = np.arange(last_index + 1, last_index + 1 + future_days).reshape(-1, 1)
    preds_future = model.predict(future_indices)

    future_dates = pd.date_range(start=end_date + pd.Timedelta(days=1), periods=future_days)
    prediction = pd.DataFrame({"Date": future_dates, "Predicted Price": preds_future})

    return prediction, hist_pred, round(mape, 2) if mape is not None else None


# === LSTM Model ===
def predict_lstm(df, years, future_days):
    import random
    import os
    import tensorflow as tf

    # Set deterministic behavior
    os.environ["PYTHONHASHSEED"] = "0"
    random.seed(0)
    np.random.seed(0)
    tf.random.set_seed(0)

    df = df[["Date", "Close"]].dropna()
    df["Date"] = pd.to_datetime(df["Date"])

    end_date = df["Date"].max()
    start_date = end_date - pd.DateOffset(years=int(years.replace("y", "")))
    df = df[df["Date"] >= start_date].copy()

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df["Close"].values.reshape(-1, 1))

    seq_length = 30
    X, y = [], []
    for i in range(seq_length, len(scaled)):
        X.append(scaled[i - seq_length:i])
        y.append(scaled[i])

    if len(X) == 0:
        return None, None, None

    X, y = np.array(X), np.array(y)

    model = tf.keras.Sequential()
    model.add(tf.keras.layers.LSTM(50, return_sequences=False, input_shape=(seq_length, 1)))
    model.add(tf.keras.layers.Dense(1))
    model.compile(optimizer="adam", loss="mse")
    model.fit(X, y, epochs=10, batch_size=16, verbose=0)

    # Predict historical
    preds_hist = model.predict(X, verbose=0)
    preds_hist = scaler.inverse_transform(preds_hist).flatten()
    actual = scaler.inverse_transform(y.reshape(-1, 1)).flatten()
    dates = df["Date"].values[-len(preds_hist):]
    mape = mean_absolute_percentage_error(actual, preds_hist) * 100 if len(actual) == len(preds_hist) else None

    hist_pred = pd.DataFrame({"Date": dates, "Predicted Price": preds_hist})

    # Predict future
    current_seq = scaled[-seq_length:]
    preds_future = []
    for _ in range(future_days):
        pred = model.predict(current_seq.reshape(1, seq_length, 1), verbose=0)
        preds_future.append(pred[0][0])
        current_seq = np.append(current_seq[1:], pred, axis=0)

    preds_future = scaler.inverse_transform(np.array(preds_future).reshape(-1, 1)).flatten()
    future_dates = pd.date_range(start=end_date + pd.Timedelta(days=1), periods=future_days)
    prediction = pd.DataFrame({"Date": future_dates, "Predicted Price": preds_future})

    return prediction, hist_pred, round(mape, 2) if mape is not None else None
