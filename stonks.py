import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import datetime
import time

# ==========================================
# CONFIGURATION & DATA
# ==========================================
INITIAL_INVESTMENT = 5000.0
BENCHMARK_TICKER = "VTTSX"

# Root 2 Proportions (1:1.414)
CHART_HEIGHT = 9
CHART_WIDTH = CHART_HEIGHT * 1.414  # ~12.73

WATCHLISTS = {
    "20241205 (15yr)": {
        "date": "20241205",
        "tickers": ["ABT", "WELL", "DHR", "CAT", "MDT", "JNJ", "GOOGL", "ADBE", "CRM", "UPS", "ACN", "JPM", "SHEL", "CVS", "TM", "UNH", "V", "AMZN", "MSFT", "AAPL", "WMT", "NVDA", "ACGBY"] # Fixed AAPL typo
    },
    "20210625": {
        "date": "20210625",
        "tickers": ["PLTR"]
    },
    "20260105 long term": {
        "date": "20260105",
        "tickers": ["XLV", "OHI", "EW", "ENSG", "BSX", "ADUS", "ALHC", "GDRX", "RKLB", "NU"]
    },
    "20190301": {
        "date": "20190301",
        "tickers": ["NFLX", "MSFT", "META", "MCD", "FDX", "TSLA", "AAPL", "ABBV", "PEP", "QCOM", "GE", "ABT", "DIS", "TIP", "SBUX", "VCIT", "BABA", "CHRW", "BND", "BLV", "GIS", "SPHD", "CMCSA", "VWO", "VZ", "BAC", "T", "F", "FLWS", "GPRO"] # Fixed AAPL typo
    }
}

NEON_COLORS = ['#00FFFF', '#FF00FF', '#00FF00', '#FFFF00', '#FF4500', '#1E90FF']

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y%m%d")

def calc_cagr(start_value, end_value, start_date, end_date):
    days = (end_date - start_date).days
    if days == 0 or start_value == 0:
        return 0.0
    years = days / 365.25
    return ((end_value / start_value) ** (1 / years)) - 1.0

def calc_max_drawdown(series):
    roll_max = series.cummax()
    drawdown = (series / roll_max) - 1.0
    return drawdown.min()

def apply_dark_theme(ax, fig=None):
    if fig:
        fig.patch.set_facecolor('#0A0A0A')
    ax.set_facecolor('#0A0A0A')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.tick_params(colors='#FFFFFF')
    ax.xaxis.label.set_color('#FFFFFF')
    ax.yaxis.label.set_color('#FFFFFF')
    ax.title.set_color('#FFFFFF')

# ==========================================
# DATA PROCESSING LOGIC
# ==========================================
def fetch_and_process_data(log_callback):
    results = {}
    
    for name, data in WATCHLISTS.items():
        log_callback(f">>> Initializing Backtest: [{name}]")
        target_dt = parse_date(data["date"])
        start_str = target_dt.strftime("%Y-%m-%d")
        tickers = data["tickers"]
        
        all_tickers = list(set(tickers + [BENCHMARK_TICKER]))
        prices_dict = {}
        
        # 1. The Polite Sequential Downloader
        for tk in all_tickers:
            log_callback(f"    Fetching {tk} data from {start_str}...")
            try:
                df = yf.download(tk, start=start_str, auto_adjust=True, progress=False)
                if not df.empty and 'Close' in df.columns:
                    if isinstance(df.columns, pd.MultiIndex):
                        prices_dict[tk] = df['Close'].iloc[:, 0]
                    else:
                        prices_dict[tk] = df['Close']
                    log_callback(f"    [OK] {tk} retrieved successfully.")
                else:
                    log_callback(f"    [WARN] {tk} returned empty dataset.")
            except Exception as e:
                log_callback(f"    [ERROR] {tk} failed: {str(e)}")
            
            # Common courtesy rate limit
            time.sleep(0.5)
            
        if not prices_dict:
            log_callback(f"    [CRITICAL] No data retrieved for {name}. Skipping.")
            continue
            
        log_callback(f"    Processing portfolio logic for [{name}]...")
        prices = pd.DataFrame(prices_dict)
        prices.index = prices.index.tz_localize(None)
        
        valid_dates = prices.index[prices.index >= target_dt]
        if len(valid_dates) == 0:
            continue
            
        end_dt = prices.index[-1]
        capital_per_ticker = INITIAL_INVESTMENT / len(tickers)
        shares = {}
        stock_stats = []
        
        # 2. Resilient Survivorship Bias & Position Sizing
        for tk in tickers:
            if tk in prices.columns:
                tk_prices = prices[tk].dropna()
                tk_valid_dates = tk_prices.index[tk_prices.index >= target_dt]
            else:
                tk_valid_dates = []

            if len(tk_valid_dates) > 0 and tk_prices.loc[tk_valid_dates[0]] > 0:
                tk_t0 = tk_valid_dates[0]
                start_price = tk_prices.loc[tk_t0]
                shrs = capital_per_ticker / start_price
                shares[tk] = shrs
                
                current_price = tk_prices.iloc[-1]
                total_return = ((current_price - start_price) / start_price) * 100
                contrib = shrs * current_price
            else:
                start_price = np.nan
                shrs = 0.0
                shares[tk] = 0.0
                current_price = 0.0
                total_return = -100.0
                contrib = 0.0

            stock_stats.append({
                "Ticker": tk,
                "Start Price": start_price,
                "Current Price": current_price,
                "Shares": shrs,
                "Total Return (%)": total_return,
                "Dollar Contribution ($)": contrib
            })
            
        # 3. VTTSX Benchmark Sizing
        if BENCHMARK_TICKER in prices.columns:
            bench_prices = prices[BENCHMARK_TICKER].dropna()
            bench_valid_dates = bench_prices.index[bench_prices.index >= target_dt]
            if len(bench_valid_dates) > 0:
                bench_t0 = bench_valid_dates[0]
                vttsx_start_price = bench_prices.loc[bench_t0]
            else:
                vttsx_start_price = 1.0
        else:
            vttsx_start_price = 1.0
            
        vttsx_shares = INITIAL_INVESTMENT / vttsx_start_price
        
        # 4. Calculate Time Series
        port_values = pd.Series(0.0, index=prices.index)
        for tk in tickers:
            if shares[tk] > 0:
                port_values = port_values.add(prices[tk].fillna(method='ffill') * shares[tk], fill_value=0)
                
        if BENCHMARK_TICKER in prices.columns:
            vttsx_values = prices[BENCHMARK_TICKER].fillna(method='ffill') * vttsx_shares
        else:
            vttsx_values = pd.Series(INITIAL_INVESTMENT, index=prices.index)
        
        port_values = port_values[port_values.index >= valid_dates[0]]
        vttsx_values = vttsx_values[vttsx_values.index >= valid_dates[0]]
        
        port_end_val = port_values.iloc[-1]
        vttsx_end_val = vttsx_values.iloc[-1]
        
        port_cagr = calc_cagr(INITIAL_INVESTMENT, port_end_val, valid_dates[0], end_dt)
        vttsx_cagr = calc_cagr(INITIAL_INVESTMENT, vttsx_end_val, valid_dates[0], end_dt)
        alpha = port_cagr - vttsx_cagr
        
        port_mdd = calc_max_drawdown(port_values)
        vttsx_mdd = calc_max_drawdown(vttsx_values)
        
        results[name] = {
            "start_date": valid_dates[0],
            "end_date": end_dt,
            "port_values": port_values,
            "vttsx_values": vttsx_values,
            "metrics": {
                "Portfolio CAGR": port_cagr,
                "VTTSX CAGR": vttsx_cagr,
                "Alpha": alpha,
                "Portfolio Max Drawdown": port_mdd,
                "VTTSX Max Drawdown": vttsx_mdd
            },
            "stock_stats": pd.DataFrame(stock_stats)
        }
        log_callback(f">>> Completed Backtest: [{name}]\n")
        
    return results

# ==========================================
# UI BUILD FUNCTIONS
# ==========================================
def build_master_summary(results):
    st.header("Master Summary")
    
    summary_data = []
    for name, data in results.items():
        m = data["metrics"]
        summary_data.append({
            "Watchlist Name": name,
            "Start Date": data["start_date"].strftime("%Y-%m-%d"),
            "Portfolio CAGR": m["Portfolio CAGR"],
            "VTTSX CAGR": m["VTTSX CAGR"],
            "Alpha": m["Alpha"],
            "Portfolio Max DD": m["Portfolio Max Drawdown"],
            "VTTSX Max DD": m["VTTSX Max Drawdown"]
        })
        
    df_summary = pd.DataFrame(summary_data)
    
    format_dict = {
        "Portfolio CAGR": "{:.2%}",
        "VTTSX CAGR": "{:.2%}",
        "Alpha": "{:.2%}",
        "Portfolio Max DD": "{:.2%}",
        "VTTSX Max DD": "{:.2%}"
    }
    st.dataframe(df_summary.style.format(format_dict), use_container_width=True)

def build_master_chart(results):
    st.subheader("Master Time-Series (Portfolio vs Benchmark)")
    
    plt.style.use('dark_background')
    # High-Res DPI & Root 2 Proportions
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT), dpi=300)
    apply_dark_theme(ax, fig)
    
    color_idx = 0
    for name, data in results.items():
        color = NEON_COLORS[color_idx % len(NEON_COLORS)]
        ax.plot(data["port_values"].index, data["port_values"], 
                color=color, linewidth=2, label=f"{name} (Port)")
        ax.plot(data["vttsx_values"].index, data["vttsx_values"], 
                color='white', alpha=0.3, linestyle='--', linewidth=1.5, label=f"VTTSX ({name[:10]}...)")
        color_idx += 1
        
    ax.set_ylabel("Portfolio Value ($)")
    ax.yaxis.set_major_formatter('${x:,.0f}')
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), frameon=False, labelcolor='white')
    
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

def build_watchlist_tabs(results):
    st.subheader("Individual Watchlist Breakdowns")
    tabs = st.tabs(list(results.keys()))
    
    for tab, (name, data) in zip(tabs, results.items()):
        with tab:
            df_stats = data["stock_stats"].sort_values(by="Dollar Contribution ($)", ascending=False).reset_index(drop=True)
            
            # High-Res DPI & Root 2 Proportions
            fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT), dpi=300)
            apply_dark_theme(ax, fig)
            
            df_chart = df_stats.sort_values(by="Total Return (%)", ascending=True)
            
            tickers = df_chart["Ticker"]
            returns = df_chart["Total Return (%)"]
            colors = ['#00FF00' if r >= 0 else '#FF4444' for r in returns]
            
            bars = ax.barh(tickers, returns, color=colors, height=0.6)
            ax.set_xlabel("Total Return (%)")
            ax.set_title(f"Individual Stock Performance: {name}")
            
            pe = [path_effects.withStroke(linewidth=2.5, foreground='black')]
            for bar, ret in zip(bars, returns):
                x_val = bar.get_width()
                y_val = bar.get_y() + bar.get_height() / 2
                offset = 2 if x_val >= 0 else -2
                ha = 'left' if x_val >= 0 else 'right'
                
                ax.text(x_val + offset, y_val, f"{ret:.2f}%", 
                        color='white', va='center', ha=ha, 
                        fontsize=8, fontweight='bold', path_effects=pe)
            
            xlim = ax.get_xlim()
            ax.set_xlim(xlim[0] * 1.15 if xlim[0] < 0 else xlim[0], xlim[1] * 1.15)
            
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            
            st.markdown("##### Composition & Contribution Data")
            format_dict = {
                "Start Price": "${:,.2f}",
                "Current Price": "${:,.2f}",
                "Shares": "{:,.4f}",
                "Total Return (%)": "{:.2f}%",
                "Dollar Contribution ($)": "${:,.2f}"
            }
            df_display = df_stats.copy()
            st.dataframe(df_display.style.format(format_dict, na_rep="N/A"), use_container_width=True)

# ==========================================
# MAIN APP EXECUTION
# ==========================================
def main():
    st.set_page_config(page_title="Portfolio Backtesting Engine", layout="wide")
    st.title("Portfolio Backtesting Engine")
    st.caption("Disclaimer: Returns assume tax-free dividend reinvestment. Missing/failed tickers are treated as a 100% loss.")
    
    # Initialize session state for caching results
    if 'backtest_results' not in st.session_state:
        st.session_state.backtest_results = None

    if st.session_state.backtest_results is None:
        st.write("### Engine Status Log")
        log_container = st.empty()
        log_lines = []
        
        def update_log(msg):
            log_lines.append(msg)
            # Keep the last 15 lines visible to simulate a rolling terminal
            display_text = "\n".join(log_lines[-15:])
            log_container.code(display_text, language="bash")

        with st.spinner("Executing pipeline..."):
            st.session_state.backtest_results = fetch_and_process_data(update_log)
            update_log(">>> ALL JOBS COMPLETE. RENDERING DASHBOARD...")
            time.sleep(1) # Brief pause so the user can read the completion message
            log_container.empty() # Clear the terminal once finished

    if st.session_state.backtest_results:
        results = st.session_state.backtest_results
        build_master_summary(results)
        st.divider()
        build_master_chart(results)
        st.divider()
        build_watchlist_tabs(results)
    else:
        st.error("Failed to load data. Please check your internet connection or ticker validity.")

if __name__ == "__main__":
    main()