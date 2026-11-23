# 🛒 Olist Text-to-SQL with a Business Glossary RAG

A Text-to-SQL chatbot that turns Korean business questions into SQL, runs them, and shows the results.
It works on the **Olist** Brazilian e-commerce dataset (~100k orders, 8 tables).

**Key finding:** Modern LLMs almost never make SQL *syntax* mistakes anymore. What they get wrong are **company-specific terms** such as "GMV" or "repeat customer", whose definitions differ from company to company and do not appear anywhere in the schema.
A **glossary RAG** that injects only the definitions relevant to each question raised execution accuracy from **67.3% to 99.3%**.

- 🔗 Demo: (link will be added after deployment)
- 🧠 Model: Claude Haiku (Anthropic API)
- 🛠 Stack: Python, SQLite, pandas, Streamlit

## Results

50-question evaluation set, each experiment run 3 times (mean ± standard deviation).

| Experiment | Overall | General questions (30) | Glossary questions (20) |
|---|---|---|---|
| Baseline: schema only | 67.3 ± 2.3% | 100.0 ± 0.0% | 18.3 ± 5.8% |
| Exp. 1: full glossary in every prompt (1 run) | 94.0% | 90.0% | 100.0% |
| **Exp. 2: glossary RAG** | **99.3 ± 1.2%** | **98.9 ± 1.9%** | **100.0 ± 0.0%** |

- In the baseline, 15 glossary questions were wrong in **all 3 runs**. This is a structural gap, not bad luck: without the definition, the model cannot get them right.
- Exp. 1 solved every glossary question, but definitions **leaked into unrelated questions**, so accuracy on general questions dropped by 10 percentage points.
- Exp. 2 injects only the terms that appear in the question, which removed that side effect. The single remaining error was correct in 2 of 3 runs and comes from an ambiguous question (see below).

## How the project evolved

### 1. An easy benchmark could not show any improvement
- The first evaluation used **Chinook**, a well-known practice database (30 questions). The baseline was already **96.7%**.
- Switching to the more realistic **Olist** dataset and adding traps (customer ID vs. actual person, Portuguese category names, split payments) still gave **93.3%**, and both errors turned out to be **grading errors** caused by month formatting (`01` vs. `2018-01`).

### 2. Finding the real weakness: business terms
- Hypothesis: in real data teams, Text-to-SQL fails on **term definitions**, not on SQL syntax.
- I wrote [`glossary.md`](glossary.md), defining 18 business terms (GMV, net revenue, AOV, active seller, repeat customer, late delivery, and more), and added 20 questions that use them.
- For every glossary question I checked that a **common-sense interpretation gives a different answer from the official definition**. Example: counting only 1-star reviews as "complaint reviews" gives 11,858, while the glossary definition (2 stars or less) gives 15,093.

### 3. Glossary RAG
[`glossary_rag.py`](glossary_rag.py)
1. Find the glossary terms mentioned in the question (e.g. "top seller").
2. Follow the terms used inside those definitions (top seller → GMV → completed order).
3. If no term is found, add nothing, so general questions get exactly the baseline prompt.

## Failures and lessons
- **The grader can be wrong too:** I manually inspected wrong answers and found correct answers marked wrong only because of output format (false negatives). I fixed this by stating the expected format in the questions.
- **Ambiguous questions split even humans:** "Delivered later than the estimated date" does not say whether to compare timestamps or dates, so the model's answer changed between runs. This is exactly why companies define "late delivery" in a glossary.
- **Model response format:** For hard questions, the response sometimes started with a thinking block, so `content[0].text` failed. I now join only the text blocks.

## Safety
- Only queries starting with `SELECT` / `WITH` are executed
- The database is opened read-only
- Queries running longer than 20 seconds are stopped
- The web demo allows 20 questions per session to protect API credits

## Files

| File | Purpose |
|---|---|
| `app.py` | Question → prompt → Claude → SQL → execution (also runs as an interactive CLI) |
| `glossary_rag.py` | Glossary retrieval, including terms referenced inside definitions |
| `glossary.md` | Business glossary (in Korean) |
| `streamlit_app.py` | Web demo |
| `evaluate.py` | Grading by comparing execution results, repeated runs, variance analysis |
| `eval_set.json` | Olist evaluation set, 50 questions (30 general + 20 glossary); every gold SQL was executed and verified |
| `eval_set_chinook.json` | Chinook evaluation set, 30 questions (early experiment) |
| `build_olist_db.py` | Builds the SQLite database (`olist.db`) from the 8 files in `data/` |
| `data/` | Olist CSV files, gzip-compressed to fit GitHub's upload limit |
| `results/` | Grading results for each experiment (CSV) |

## How to run

```bash
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

# Put your API key in a .env file
# ANTHROPIC_API_KEY=...

python build_olist_db.py         # build olist.db
streamlit run streamlit_app.py   # web demo
python evaluate.py --mode rag --repeat 3 --name exp2_rag   # evaluation
```

`--mode` is one of `none` (baseline), `full` (whole glossary), or `rag` (glossary RAG).

## Data
[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (CC BY-NC-SA 4.0).
The geolocation file is not used.
