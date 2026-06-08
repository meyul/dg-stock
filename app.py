import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ----------------------------
# 페이지 기본 설정
# ----------------------------
st.set_page_config(
    page_title="한미 주식 비교 분석",
    page_icon="📈",
    layout="wide"
)

st.title("📈 한국 & 미국 주요 주식 비교 분석")
st.markdown("야후 파이낸스(yfinance) 데이터를 활용한 수익률 & 차트 비교 웹앱")

# ----------------------------
# 주요 종목 사전 정의
# ----------------------------
KR_STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "현대차": "005380.KS",
    "NAVER": "035420.KS",
    "카카오": "035720.KS",
}

US_STOCKS = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Tesla": "TSLA",
    "Amazon": "AMZN",
    "Google": "GOOGL",
}

# ----------------------------
# 사이드바: 사용자 입력
# ----------------------------
st.sidebar.header("⚙️ 설정")

selected_kr = st.sidebar.multiselect(
    "🇰🇷 한국 주식 선택",
    options=list(KR_STOCKS.keys()),
    default=["삼성전자", "SK하이닉스"]
)

selected_us = st.sidebar.multiselect(
    "🇺🇸 미국 주식 선택",
    options=list(US_STOCKS.keys()),
    default=["Apple", "NVIDIA"]
)

# 기간 선택
period_option = st.sidebar.selectbox(
    "📅 분석 기간",
    options=["1개월", "3개월", "6개월", "1년", "3년"],
    index=3
)

period_map = {
    "1개월": 30,
    "3개월": 90,
    "6개월": 180,
    "1년": 365,
    "3년": 365 * 3
}

end_date = datetime.now()
start_date = end_date - timedelta(days=period_map[period_option])

# ----------------------------
# 데이터 불러오기 함수 (캐싱)
# ----------------------------
@st.cache_data(ttl=3600)  # 1시간 캐싱
def load_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            return None
        # 멀티인덱스 컬럼 처리 (yfinance 버전에 따라 발생)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        st.warning(f"{ticker} 데이터 로드 실패: {e}")
        return None

# ----------------------------
# 선택한 종목 합치기
# ----------------------------
selected_all = {}
for name in selected_kr:
    selected_all[name] = KR_STOCKS[name]
for name in selected_us:
    selected_all[name] = US_STOCKS[name]

if not selected_all:
    st.info("👈 사이드바에서 비교할 주식을 1개 이상 선택해주세요!")
    st.stop()

# ----------------------------
# 데이터 수집
# ----------------------------
price_data = {}
return_data = {}

with st.spinner("데이터를 불러오는 중..."):
    for name, ticker in selected_all.items():
        df = load_data(ticker, start_date, end_date)
        if df is not None and not df.empty:
            price_data[name] = df
            # 누적 수익률 계산 (시작일 기준 정규화)
            close = df["Close"]
            normalized = (close / close.iloc[0] - 1) * 100
            return_data[name] = normalized

if not price_data:
    st.error("선택한 종목의 데이터를 불러올 수 없습니다.")
    st.stop()

# ----------------------------
# 1. 누적 수익률 비교 차트
# ----------------------------
st.subheader("📊 누적 수익률 비교 (%)")

fig_return = go.Figure()
for name, returns in return_data.items():
    fig_return.add_trace(go.Scatter(
        x=returns.index,
        y=returns.values,
        mode="lines",
        name=name,
        hovertemplate="%{y:.2f}%<extra></extra>"
    ))

fig_return.update_layout(
    xaxis_title="날짜",
    yaxis_title="누적 수익률 (%)",
    hovermode="x unified",
    height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
fig_return.add_hline(y=0, line_dash="dash", line_color="gray")
st.plotly_chart(fig_return, use_container_width=True)

# ----------------------------
# 2. 수익률 요약 테이블
# ----------------------------
st.subheader("📋 수익률 요약")

summary = []
for name, returns in return_data.items():
    total_return = returns.iloc[-1]
    summary.append({
        "종목": name,
        "시작가": round(float(price_data[name]["Close"].iloc[0]), 2),
        "현재가": round(float(price_data[name]["Close"].iloc[-1]), 2),
        f"{period_option} 수익률(%)": round(float(total_return), 2)
    })

summary_df = pd.DataFrame(summary)
st.dataframe(
    summary_df.style.format(precision=2),
    use_container_width=True,
    hide_index=True
)

# ----------------------------
# 3. 개별 캔들스틱 차트
# ----------------------------
st.subheader("🕯️ 개별 종목 캔들스틱 차트")

selected_chart = st.selectbox(
    "차트를 볼 종목 선택",
    options=list(price_data.keys())
)

df_chart = price_data[selected_chart]

fig_candle = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=[0.7, 0.3],
    subplot_titles=("주가", "거래량")
)

fig_candle.add_trace(
    go.Candlestick(
        x=df_chart.index,
        open=df_chart["Open"],
        high=df_chart["High"],
        low=df_chart["Low"],
        close=df_chart["Close"],
        name="주가"
    ),
    row=1, col=1
)

fig_candle.add_trace(
    go.Bar(
        x=df_chart.index,
        y=df_chart["Volume"],
        name="거래량",
        marker_color="lightblue"
    ),
    row=2, col=1
)

fig_candle.update_layout(
    height=600,
    xaxis_rangeslider_visible=False,
    title=f"{selected_chart} 차트"
)
st.plotly_chart(fig_candle, use_container_width=True)

# ----------------------------
# 푸터
# ----------------------------
st.markdown("---")
st.caption("📌 데이터 출처: Yahoo Finance | 본 자료는 투자 권유가 아닙니다.")
