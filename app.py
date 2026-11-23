import os
import re
import sqlite3

import anthropic
import pandas as pd
from dotenv import load_dotenv

from glossary_rag import build_glossary_context, parse_glossary

# ── 0. 준비: API 키와 DB 연결 ─────────────────────────
DB_PATH = "olist.db"   # Chinook으로 돌아가려면 "chinook.db"
MODEL = "claude-haiku-5-5"

# 실험 설정: 용어 사전을 프롬프트에 어떻게 넣을지
#   "none" → 베이스라인 (스키마만)
#   "full" → 실험 1 (용어 사전 전체를 항상 전달)
#   "rag"  → 실험 2 (질문에 나온 용어의 정의만 골라 전달)
GLOSSARY_MODE = "rag"
GLOSSARY_PATH = "glossary.md"

load_dotenv(override=True)
key = os.getenv("ANTHROPIC_API_KEY")
os.environ.pop("ANTHROPIC_API_KEY", None)
client = anthropic.Anthropic(auth_token=key)

conn = sqlite3.connect(DB_PATH)


# ── 1. 스키마 읽기: DB에 어떤 테이블과 컬럼이 있는지 ─────
def get_schema():
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ).fetchall()
    return "\n\n".join(r[0] for r in rows)


SCHEMA = get_schema()


with open(GLOSSARY_PATH, encoding="utf-8") as f:
    GLOSSARY_FULL = f.read()
COMMON_RULES, GLOSSARY_ENTRIES = parse_glossary(GLOSSARY_PATH)


def get_glossary(question, mode=None):
    """모드에 따라 프롬프트에 넣을 용어 사전과, 사용한 용어 이름 목록을 돌려줍니다.
    mode를 주지 않으면 맨 위의 GLOSSARY_MODE 설정을 씁니다."""
    mode = mode or GLOSSARY_MODE
    if mode == "full":
        return GLOSSARY_FULL, ["(전체)"]
    if mode == "rag":
        return build_glossary_context(question, COMMON_RULES, GLOSSARY_ENTRIES)
    return "", []


# ── 2. 질문 → SQL: Claude에게 SQL 만들어 달라고 요청 ────
def build_prompt(question, mode=None):
    glossary, _ = get_glossary(question, mode)
    parts = [
        "당신은 SQLite 전문가입니다.",
        "아래 데이터베이스 스키마를 보고, 질문에 답하는 SQLite 쿼리를 작성하세요.",
    ]
    if glossary:
        parts.append("질문에 용어 사전의 용어가 나오면 반드시 사전의 정의대로 계산하세요.")
    parts.append("설명 없이 SQL 하나만 출력하세요.")
    parts.append(f"\n[스키마]\n{SCHEMA}")
    if glossary:
        parts.append(f"\n[용어 사전]\n{glossary}")
    parts.append(f"\n[질문]\n{question}")
    return "\n".join(parts)


def text_to_sql(question, mode=None):
    prompt = build_prompt(question, mode)
    res = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    # 여러 조각 중 '답변(text)' 조각만 모으기 (생각 블록은 건너뜀)
    answer = "".join(block.text for block in res.content if block.type == "text")
    return clean_sql(answer)


# ── 3. SQL 정리: ```sql 같은 표시 지우기 ───────────────
def clean_sql(text):
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    return text.strip().rstrip(";")


# ── 4. 안전장치: 읽기(SELECT)만 허용 ───────────────────
def is_safe(sql):
    words = sql.strip().split()
    return bool(words) and words[0].upper() in ("SELECT", "WITH")


# ── 5. 실행: DB에서 SQL을 돌려 결과 표 만들기 ──────────
def run_sql(sql):
    return pd.read_sql(sql, conn)


# ── 6. 전체 흐름 ───────────────────────────────────────
def ask(question):
    _, terms = get_glossary(question)
    print(f"\n📖 사용한 용어: {', '.join(terms) if terms else '없음'}")
    sql = text_to_sql(question)
    print("\n🧠 생성된 SQL:\n", sql)

    if not is_safe(sql):
        print("⛔ SELECT 쿼리만 실행할 수 있어요.")
        return

    try:
        result = run_sql(sql)
        print("\n📊 결과:")
        print(result.head(20).to_string(index=False))
    except Exception as e:
        print("❌ 실행 오류:", e)


if __name__ == "__main__":
    print(f"[{DB_PATH} / 용어 사전: {GLOSSARY_MODE}] 질문을 입력하세요. 끝내려면 q를 입력하세요.")
    while True:
        q = input("\n❓ 질문: ").strip()
        if q.lower() == "q":
            break
        if q:
            ask(q)
