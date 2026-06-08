import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ----------------------------
# 페이지 설정
# ----------------------------
st.set_page_config(page_title="AI 종목 추천", page_icon="🤖", layout="wide")

st.title("🤖 AI 종목 추천 (지표 기반 점수 모델)")
st.markdown(
    "여러 투자 지표를 종합 분석해 **점수가 높은 순으로 종목을 추천**합니다.\n\n"
    "> ⚠️ 본 추천은 학습용이며 투자 권유가 아닙니다."
)

# ----------------------------
# 종목 사전
# ----------------------------
KR_STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "현대차": "005380.KS",
    "NAVER": "035420.KS",
    "카카오": "035720.KS",
    "기아": "000270.KS",
    "POSCO홀딩스": "005490.KS",
}

US_STOCKS = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Tesla": "TSLA",
    "Amazon": "AMZN",
    "Google": "GOOGL",
    "Meta": "META",
    "AMD": "AMD",
}

ALL_STOCKS = {**KR_STOCKS, **US_STOCKS}

# ----------------------------
# 사이드바: 투자 성향 선택
# ----------------------------
st.sidebar.header("⚙️ 추천 설정")

market = st.sidebar.radio("시장 선택", ["전체", "한국", "미국"])

invest_style = st.sidebar.radio(
    "투자 성향",
    ["안정형 (변동성 낮은 종목 선호)",
     "공격형 (모멘텀 높은 종목 선호)",
     "균형형 (안정성+모멘텀 균형)"]
)

top_n = st.sidebar.slider("추천 종목 개수", 1, 8, 3)

# ----------------------------
# 분석 대상 종목 결정
# ----------------------------
if market == "한국":
    target_stocks = KR_STOCKS
elif market == "미국":
    target_stocks = US_STOCKS
else:
    target_stocks = ALL_STOCKS

# ----------------------------
# 데이터 로드 (캐싱)
# ----------------------------
@st.cache_data(ttl=3600)
def load_data(ticker):
    try:
        end = datetime.now()
        start = end - timedelta(days=180)  # 6개월
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None

# ----------------------------
# RSI 계산 함수
# ----------------------------
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ----------------------------
# 지표 계산
# ----------------------------
def analyze_stock(df):
    close = df["Close"]

    # 1) 모멘텀: 최근 1개월 수익률(%)
    momentum = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 21 else 0

    # 2) 변동성: 일간 수익률 표준편차(%) (연율화)
    daily_ret = close.pct_change().dropna()
    volatility = daily_ret.std() * np.sqrt(252) * 100

    # 3) RSI
    rsi = calculate_rsi(close).iloc[-1]

    # 4) 6개월 누적 수익률(%)
    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100

    return {
        "모멘텀(1개월,%)": round(float(momentum), 2),
        "변동성(연,%)": round(float(volatility), 2),
        "RSI": round(float(rsi), 2),
        "6개월수익률(%)": round(float(total_return), 2),
        "현재가": round(float(close.iloc[-1]), 2)
    }

# ----------------------------
# 점수 계산 함수
# ----------------------------
def calculate_score(metrics, style):
    momentum = metrics["모멘텀(1개월,%)"]
    volatility = metrics["변동성(연,%)"]
    rsi = metrics["RSI"]
    total_return = metrics["6개월수익률(%)"]

    # 각 지표를 점수화 (0~100 스케일 가정)
    # 모멘텀 점수: 높을수록 좋음
    momentum_score = np.clip(50 + momentum * 2, 0, 100)

    # 안정성 점수: 변동성 낮을수록 좋음 (변동성 40% 기준)
    stability_score = np.clip(100 - volatility * 1.5, 0, 100)

    # RSI 점수: 50 근처가 이상적 (과매수/과매도 회피)
    rsi_score = np.clip(100 - abs(rsi - 50) * 2, 0, 100)

    # 누적수익률 점수
    return_score = np.clip(50 + total_return, 0, 100)

    # 투자 성향별 가중치
    if "안정형" in style:
        weights = {"momentum": 0.2, "stability": 0.5, "rsi": 0.2, "return": 0.1}
    elif "공격형" in style:
        weights = {"momentum": 0.5, "stability": 0.1, "rsi": 0.1, "return": 0.3}
    else:  # 균형형
        weights = {"momentum": 0.3, "stability": 0.3, "rsi": 0.2, "return": 0.2}

    total_score = (
        momentum_score * weights["momentum"] +
        stability_score * weights["stability"] +
        rsi_score * weights["rsi"] +
        return_score * weights["return"]
    )
    return round(total_score, 1)

# ----------------------------
# 분석 실행
# ----------------------------
if st.button("🔍 AI 추천 분석 시작", type="primary"):
    results = []
    progress = st.progress(0)
    status = st.empty()

    total = len(target_stocks)
    for i, (name, ticker) in enumerate(target_stocks.items()):
        status.text(f"분석 중... {name}")
        df = load_data(ticker)
        if df is not None and len(df) > 21:
            metrics = analyze_stock(df)
            score = calculate_score(metrics, invest_style)
            results.append({
                "종목": name,
                "AI점수": score,
                **metrics
            })
        progress.progress((i + 1) / total)

    status.empty()
    progress.empty()

    if not results:
        st.error("데이터를 불러올 수 없습니다. 잠시 후 다시 시도해주세요.")
        st.stop()

    # 점수순 정렬
    result_df = pd.DataFrame(results).sort_values("AI점수", ascending=False).reset_index(drop=True)

    # ----------------------------
    # 추천 결과 출력
    # ----------------------------
    st.subheader(f"🏆 추천 종목 TOP {top_n}")

    top_df = result_df.head(top_n)

    # 추천 종목 카드 형태로 표시
    cols = st.columns(min(top_n, 4))
    for idx, row in top_df.iterrows():
        col = cols[idx % len(cols)]
        with col:
            st.metric(
                label=f"{idx+1}위 · {row['종목']}",
                value=f"{row['AI점수']}점",
                delta=f"{row['6개월수익률(%)']}% (6개월)"
            )

    # ----------------------------
    # 점수 막대 차트
    # ----------------------------
    st.subheader("📊 전체 종목 AI 점수 비교")
    fig = go.Figure(go.Bar(
        x=result_df["AI점수"],
        y=result_df["종목"],
        orientation="h",
        marker_color=result_df["AI점수"],
        marker_colorscale="Viridis",
        text=result_df["AI점수"],
        textposition="auto"
    ))
    fig.update_layout(
        xaxis_title="AI 점수",
        yaxis_title="종목",
        height=400 + len(result_df) * 20,
        yaxis=dict(autorange="reversed")
    )
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------
    # 상세 지표 테이블
    # ----------------------------
    st.subheader("📋 전체 분석 결과")
    st.dataframe(
        result_df.style.background_gradient(subset=["AI점수"], cmap="Greens"),
        use_container_width=True,
        hide_index=True
    )

    # ----------------------------
    # 추천 근거 설명
    # ----------------------------
    st.subheader("💡 추천 근거")
    best = top_df.iloc[0]
    st.info(
        f"**{best['종목']}** 이(가) **{invest_style.split('(')[0].strip()}** 성향에 "
        f"가장 적합한 종목으로 분석되었습니다.\n\n"
        f"- 모멘텀(1개월): {best['모멘텀(1개월,%)']}%\n"
        f"- 변동성(연): {best['변동성(연,%)']}%\n"
        f"- RSI: {best['RSI']} (50 근처일수록 안정적)\n"
        f"- 6개월 수익률: {best['6개월수익률(%)']}%"
    )

else:
    st.info("👈 사이드바에서 설정을 마친 후 **[AI 추천 분석 시작]** 버튼을 눌러주세요!")

# ----------------------------
# 지표 설명
# ----------------------------
with st.expander("📚 사용된 지표 설명 보기"):
    st.markdown("""
    | 지표 | 의미 |
    |------|------|
    | **모멘텀** | 최근 1개월간 가격 상승률. 높을수록 상승 추세 |
    | **변동성** | 가격이 얼마나 출렁이는지. 낮을수록 안정적 |
    | **RSI** | 상대강도지수. 70↑ 과매수, 30↓ 과매도 |
    | **6개월 수익률** | 6개월 전 대비 가격 상승률 |

    **AI 점수**는 위 지표들을 투자 성향에 따라 **가중 평균**하여 0~100점으로 계산합니다.
    """)

st.markdown("---")
st.caption("📌 데이터: Yahoo Finance | 학습용 시뮬레이션입니다.")
