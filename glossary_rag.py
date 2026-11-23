"""용어 사전 RAG: 질문에 나온 용어의 정의만 골라 프롬프트에 넣습니다.

glossary.md 구조
  ## 공통 규칙        → 용어가 하나라도 검색되면 함께 넣는 기본 규칙
  ## 그 밖의 섹션     → "- **용어**: 정의" 형식의 용어 항목
용어 이름에 괄호가 있으면 괄호 안도 별칭으로 검색합니다. 예: 객단가(AOV) → 객단가, AOV
"""
import re

COMMON_SECTION = "공통 규칙"


def parse_glossary(path="glossary.md"):
    """glossary.md를 읽어 (공통 규칙 목록, 용어 항목 목록)으로 나눕니다."""
    common, entries = [], []
    section = ""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            m = re.match(r"- \*\*(.+?)\*\*\s*:\s*(.+)", line)
            if not m:
                continue
            name, definition = m.group(1).strip(), m.group(2).strip()
            if section == COMMON_SECTION:
                common.append(line)
                continue
            aliases = [re.sub(r"\(.*?\)", "", name).strip()]
            aliases += re.findall(r"\((.*?)\)", name)
            entries.append({"name": name, "aliases": aliases, "line": line})
    return common, entries


def _mentions(text, entry):
    t = text.lower()
    return any(a.lower() in t for a in entry["aliases"] if a)


def retrieve(question, common, entries):
    """질문에 나온 용어를 찾고, 그 정의 안에 나오는 다른 용어까지 따라가서 모읍니다.
    예: '우수 판매자' → 정의에 'GMV'가 있음 → 'GMV' → 정의에 '완료 주문'이 있음 → '완료 주문'
    """
    hits = [e for e in entries if _mentions(question, e)]
    changed = True
    while changed:
        changed = False
        for e in entries:
            if e not in hits and any(_mentions(h["line"], e) for h in hits):
                hits.append(e)
                changed = True
    return hits


def build_glossary_context(question, common, entries):
    """프롬프트에 넣을 용어 사전 부분을 만듭니다. 관련 용어가 없으면 빈 문자열."""
    hits = retrieve(question, common, entries)
    if not hits:
        return "", []
    text = "## 공통 규칙\n" + "\n".join(common) + "\n\n## 관련 용어\n"
    text += "\n".join(e["line"] for e in hits)
    return text, [e["name"] for e in hits]
