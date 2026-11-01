import streamlit as st
import pandas as pd
import numpy as np
import ccxt
import time

st.set_page_config(layout="wide")
st.title("Binance Smart Money Scanner")

# -----------------------------
# Config
# -----------------------------
SELECTED_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
    "LINK/USDT", "DOT/USDT", "MATIC/USDT", "NEAR/USDT",
    "UNI/USDT", "LTC/USDT", "FIL/USDT", "ATOM/USDT",
    "TRX/USDT", "ALGO/USDT", "EOS/USDT", "THETA/USDT"
]

exchange = ccxt.binance({
    "enableRateLimit": True,
    "timeout": 20000
})

# -----------------------------
# Helper functions
# -----------------------------
def get_ohlcv(symbol, tf="1h", limit=200):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        df = pd.DataFrame(data, columns=["ts","open","high","low","close","volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df
    except Exception:
        return None

def trend_direction(df):
    if df is None or df.empty:
        return "Neutral"
    if df["close"].iloc[-1] > df["close"].iloc[-2]:
        return "Bullish"
    elif df["close"].iloc[-1] < df["close"].iloc[-2]:
        return "Bearish"
    return "Neutral"

def liquidity_sweep(df, lookback=20):
    if df is None or len(df) < lookback + 2:
        return False, "None", None

    recent_high = df["high"].tail(lookback).max()
    recent_low = df["low"].tail(lookback).min()
    last_close = df["close"].iloc[-1]
    last_low = df["low"].iloc[-1]
    last_high = df["high"].iloc[-1]

    bullish_sweep = (last_low < recent_low) and (last_close > recent_low)
    bearish_sweep = (last_high > recent_high) and (last_close < recent_high)

    if bullish_sweep:
        return True, "Bullish", recent_low
    elif bearish_sweep:
        return True, "Bearish", recent_high
    return False, "None", None

def bos_check(df, lookback=10):
    if df is None or len(df) < lookback + 1:
        return False, "None"

    recent_high = df["high"].tail(lookback).max()
    recent_low = df["low"].tail(lookback).min()
    last_close = df["close"].iloc[-1]

    if last_close > recent_high:
        return True, "Bullish"
    elif last_close < recent_low:
        return True, "Bearish"
    return False, "None"

def volume_confirm(df, mult=1.2):
    if df is None or len(df) < 20:
        return False
    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    last_vol = df["volume"].iloc[-1]
    return last_vol > avg_vol * mult

def analyze_symbol(symbol):
    df_1h = get_ohlcv(symbol, "1h", 200)
    df_4h = get_ohlcv(symbol, "4h", 200)
    df_1d = get_ohlcv(symbol, "1d", 200)

    if df_1h is None or df_4h is None or df_1d is None:
        return None

    score = 0
    reasons = []

    trend_1d = trend_direction(df_1d)
    if trend_1d == "Bullish":
        score += 2
        reasons.append("1D Bullish")
    elif trend_1d == "Bearish":
        score += 2
        reasons.append("1D Bearish")

    trend_4h = trend_direction(df_4h)
    if trend_4h == "Bullish":
        score += 2
        reasons.append("4H Bullish")
    elif trend_4h == "Bearish":
        score += 2
        reasons.append("4H Bearish")

    sweep_ok, sweep_dir, sweep_level = liquidity_sweep(df_1h)
    if sweep_ok:
        score += 2
        reasons.append(f"1H Sweep {sweep_dir}")

    bos_ok, bos_dir = bos_check(df_1h)
    if bos_ok:
        score += 2
        reasons.append(f"BOS {bos_dir}")

    if volume_confirm(df_1h):
        score += 2
        reasons.append("Volume Confirmed")

    current_price = df_1h["close"].iloc[-1]

    if trend_1d == "Bullish" and sweep_ok:
        signal = "Long"
    elif trend_1d == "Bearish" and sweep_ok:
        signal = "Short"
    else:
        signal = "Wait"

    return {
        "Symbol": symbol,
        "Price": round(current_price, 6),
        "1D Trend": trend_1d,
        "4H Trend": trend_4h,
        "1H Sweep": "Yes" if sweep_ok else "No",
        "1H BOS": "Yes" if bos_ok else "No",
        "Volume Confirmed": "Yes" if volume_confirm(df_1h) else "No",
        "Score": score,
        "Signal": signal,
        "Reasons": ", ".join(reasons)
    }

st.sidebar.header("Scanner Controls")
min_score = st.sidebar.slider("Minimum score", 0, 10, 6)
auto_refresh = st.sidebar.checkbox("Auto refresh every 60 seconds", value=False)

if auto_refresh:
    placeholder = st.empty()

while True:
    results = []
    for symbol in SELECTED_SYMBOLS:
        result = analyze_symbol(symbol)
        if result is not None and result["Score"] >= min_score:
            results.append(result)

    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.subheader("Strong setups")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No strong setups found for current filters.")

    if not auto_refresh:
        break

    placeholder.caption("Auto-refreshing every 60 seconds...")
    time.sleep(60)
