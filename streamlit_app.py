"""Olist Text-to-SQL 챗봇 웹 화면.

내 컴퓨터에서 실행:  streamlit run streamlit_app.py
"""
import os
import sqlite3
import time

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Olist Text-to-SQL", page_icon="🛒", layout="wide")

# ── 배포 환경: Streamlit Secrets에 넣은 API 키를 환경변수로 옮기기 ──
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass  # 내 컴퓨터에서는 Secrets 대신 .env 파일을 씀

# ── DB가 없으면 data 폴더의 CSV로 만들기 (배포 환경의 첫 실행) ──
if not os.path.exists("olist.db"):
    with st.spinner("처음 실행이라 데이터베이스를 만드는 중이에요. 1분 정도 걸려요..."):
        import build_olist_db
        build_olist_db.main()

import app  # noqa: E402  (DB가 준비된 다음에 불러와야 함)

MODES = {
    "용어 사전 RAG (최종 버전)": "rag",
    "용어 사전 없음 (베이스라인)": "none",
}
EXAMPLES = [
    "2018년 GMV는?",
    "재구매 고객은 몇 명이야?",
    "우수 판매자는 몇 명이야?",
    "불만 리뷰 비율(%)은?",
    "2018년 월별 주문 건수를 보여줘 (월은 01~12 형식으로)",
    "영어 카테고리 이름 기준으로 판매된 상품 수가 가장 많은 카테고리 5개와 그 수는?",
]
MAX_ROWS = 1000
MAX_QUESTIONS = 20  # 방문자 한 명이 한 번 접속해서 할 수 있는 질문 수 (API 비용 보호)
TIMEOUT_SEC = 20


def run_query(sql):
    """읽기 전용으로 쿼리를 실행합니다. 20초가 넘으면 중단합니다."""
    conn = sqlite3.connect(f"file:{app.DB_PATH}?mode=ro", uri=True)
    start = time.time()
    conn.set_progress_handler(lambda: int(time.time() - start > TIMEOUT_SEC), 100000)
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


def show_chart(df):
    """결과 모양에 맞춰 차트를 하나 그립니다. 맞는 모양이 없으면 표만 보여줍니다."""
    if df.shape == (1, 1):  # 숫자 하나 → 큰 숫자로
        value = df.iloc[0, 0]
        if isinstance(value, float):
            value = f"{value:,.2f}"
        elif isinstance(value, int):
            value = f"{value:,}"
        st.metric(label=str(df.columns[0]), value=value)
        return
    if df.shape[1] != 2 or len(df) < 2 or len(df) > 50:
        return
    label_col, value_col = df.columns
    if not pd.api.types.is_numeric_dtype(df[value_col]):
        return
    data = df.set_index(label_col)[value_col]
    labels = df[label_col].astype(str)
    if labels.str.fullmatch(r"\d{2}|\d{4}(-\d{2})?").all():  # 월·연도 → 선 그래프
        st.line_chart(data)
    else:  # 항목 비교 → 막대 그래프
        st.bar_chart(data, horizontal=True)


# ── 사이드바 ──
with st.sidebar:
    st.header("설정")
    mode_label = st.radio("용어 사전", list(MODES), index=0)
    mode = MODES[mode_label]
    st.caption("베이스라인으로 바꿔서 같은 질문을 해 보면, 용어 사전이 왜 필요한지 바로 보여요.")

    with st.expander("📖 용어 사전 보기"):
        st.markdown(app.GLOSSARY_FULL)

    st.subheader("평가 결과")
    st.caption("50문항 평가셋, 3회 반복 평균")
    st.dataframe(
        pd.DataFrame(
            {
                "실험": ["베이스라인", "용어 사전 RAG"],
                "전체(%)": [67.3, 99.3],
                "용어 질문(%)": [18.3, 100.0],
            }
        ),
        hide_index=True,
    )

# ── 본문 ──
st.title("🛒 Olist Text-to-SQL 챗봇")
st.write(
    "브라질 이커머스 Olist 데이터(주문 약 10만 건)에 한국어로 질문하면, "
    "Claude가 SQL을 만들어 실행하고 결과를 보여줘요. "
    "GMV, 재구매 고객 같은 회사 용어는 용어 사전의 정의대로 계산해요."
)

st.write("**예시 질문** (누르면 바로 실행돼요)")
clicked = None
cols = st.columns(3)
for i, example in enumerate(EXAMPLES):
    if cols[i % 3].button(example, key=f"ex{i}", width="stretch"):
        clicked = example
        st.session_state.question = example

with st.form("ask"):
    typed = st.text_input("질문", key="question", placeholder="예: 2017년 순매출은?")
    submitted = st.form_submit_button("질문하기", type="primary")

question = clicked or (typed.strip() if submitted else "")

if question:
    st.session_state.count = st.session_state.get("count", 0) + 1
    if st.session_state.count > MAX_QUESTIONS:
        st.warning(f"데모에서는 한 번 접속에 질문을 {MAX_QUESTIONS}개까지 할 수 있어요.")
        st.stop()

    _, terms = app.get_glossary(question, mode)
    st.write("📖 **사용한 용어:** " + (", ".join(terms) if terms else "없음"))

    with st.spinner("SQL을 만드는 중이에요..."):
        try:
            sql = app.text_to_sql(question, mode)
        except Exception as e:
            st.error(f"Claude API 호출 중 오류가 났어요: {e}")
            st.stop()

    st.write("🧠 **생성된 SQL**")
    st.code(sql, language="sql")

    if not app.is_safe(sql):
        st.warning("⛔ 데이터를 읽는 SELECT 쿼리만 실행할 수 있어요.")
        st.stop()

    try:
        df = run_query(sql)
    except Exception as e:
        message = "시간 초과" if str(e) == "interrupted" else str(e)
        st.error(f"❌ 실행 오류: {message}")
        st.stop()

    st.write(f"📊 **결과** ({len(df):,}행)")
    show_chart(df)
    st.dataframe(df.head(MAX_ROWS), hide_index=True, width="stretch")
