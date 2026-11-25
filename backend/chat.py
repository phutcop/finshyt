"""
chat.py

Role 3's core chatbot logic.

Design (matches the functional spec, Function 9):
- The AI never does arithmetic itself and never invents figures.
  The summary pack (or, in v1, the database) computes; the LLM only narrates.
- Three question paths:
    1. what-if      -> pure Python arithmetic on summary_pack, then LLM phrases it
    2. answerable    -> relevant slice of summary_pack handed to LLM, LLM answers
                        strictly from what it's given
    3. unanswerable  -> graceful refusal, no LLM call needed
- v0 only (per spec): everything is answered from the precomputed summary
  pack, no live DB queries yet. v1 (query generation) is a later swap-in
  behind the same answer_question() function signature.
"""

import json
import os
import re

import requests
from dotenv import load_dotenv
from groq import Groq
from typing import Optional

# Load .env here too (not just in main.py) so this module works whether
# it's imported by the FastAPI app or run/imported standalone (e.g. by
# run_eval.py). load_dotenv() is safe to call more than once.
load_dotenv()

# Role 2's live aggregate endpoints.
INTEL_BASE_URL = os.environ.get("INTEL_BASE_URL", "http://localhost:8001/api/intel")
SUMMARY_API_URL = os.environ.get("SUMMARY_API_URL", f"{INTEL_BASE_URL}/summary")

api_key = os.environ.get("GROQ_API_KEY", "dummy_key")
client = Groq(api_key=api_key)
MODEL = "openai/gpt-oss-120b"  # swap freely; check console.groq.com/docs/models for current options

MONTH_NAME_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def load_summary_pack() -> dict:
    """Pulls the real, live summary pack from Role 2's endpoint instead
    of a static local file. Falls back to the static file only if the
    live endpoint is unreachable, so local dev never fully breaks."""
    try:
        resp = requests.get(SUMMARY_API_URL, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[warn] couldn't reach {SUMMARY_API_URL} ({e}), falling back to local summary.json")
        summary_path = os.path.join(os.path.dirname(__file__), "summary.json")
        if not os.path.exists(summary_path):
            summary_path = "summary.json"
        with open(summary_path) as f:
            return json.load(f)


def _safe_get(url: str):
    """Best-effort GET — returns None on any failure instead of raising,
    since these are optional context enrichments, not the core answer path."""
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def extract_month_from_question(question: str) -> Optional[str]:
    """Finds an explicit month reference like 'February 2025' or '2025-02'
    in the question and returns it as 'YYYY-MM', or None if none found."""
    m = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", question)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    m2 = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\.?\s+(20\d{2})\b",
        question,
        re.IGNORECASE,
    )
    if m2:
        key = m2.group(1)[:4].lower().rstrip(".")
        key = key[:3] if key not in MONTH_NAME_TO_NUM else key
        num = MONTH_NAME_TO_NUM.get(key[:3])
        if num:
            return f"{m2.group(2)}-{num:02d}"
    return None


def _mentioned_months(question: str, default_year: int) -> list[str]:
    """Resolve named and ISO months, including 'February to March 2028'."""
    year_hints = re.findall(r"\b20\d{2}\b", question)
    inferred_year = int(year_hints[0]) if len(set(year_hints)) == 1 else default_year
    found = []
    for match in re.finditer(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", question):
        found.append((match.start(), f"{match.group(1)}-{match.group(2)}"))
    names = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
             r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sept?(?:ember)?|"
             r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
    for match in re.finditer(rf"\b({names})\b\.?\s*(20\d{{2}})?", question, re.IGNORECASE):
        number = MONTH_NAME_TO_NUM.get(match.group(1)[:3].lower())
        if number:
            found.append((match.start(), f"{int(match.group(2) or inferred_year)}-{number:02d}"))
    return list(dict.fromkeys(value for _, value in sorted(found)))


def _scoped_summary(question: str, selected_year: Optional[int] = None):
    """Build advisor evidence from one calendar year of confirmed expenses."""
    from aggregates import load_expenses, load_budgets, summary_pack, top_vendors

    expenses = load_expenses()
    budgets = load_budgets()
    available_years = sorted(expenses["date"].dt.year.unique().tolist())
    requested_years = re.findall(r"\b20\d{2}\b", question)
    year = int(requested_years[-1]) if requested_years else (selected_year or (available_years[-1] if available_years else None))
    if year is None:
        return None, None, None, None, available_years
    year_expenses = expenses[expenses["date"].dt.year == year]
    if year_expenses.empty:
        return None, None, None, year, available_years
    pack = summary_pack(year_expenses, budgets)
    pack["year"] = year
    pack["top_vendors_annual"] = top_vendors(year_expenses, n=10000)
    return pack, year_expenses, budgets, year, available_years


def load_context(question: str, base_summary: dict) -> dict:
    """Builds the full context handed to the LLM: the base summary pack,
    PLUS true annual vendor totals (the summary pack's own 'top_vendors'
    is only for its current month — see /api/intel/vendors for the
    all-time version), PLUS a specific past month's budget-vs-actual if
    the question names one (the summary pack only covers its current
    month by default)."""
    context = dict(base_summary)

    if "top_vendors_annual" not in context:
        annual_vendors = _safe_get(f"{INTEL_BASE_URL}/vendors")
        if annual_vendors:
            context["top_vendors_annual"] = annual_vendors.get("data", annual_vendors)

    month = extract_month_from_question(question)
    if month:
        budget_month = _safe_get(f"{INTEL_BASE_URL}/budget/{month}")
        if budget_month:
            context[f"budget_vs_actual_{month}"] = budget_month.get("data", budget_month)

    return context


# ---------------------------------------------------------------------------
# Question routing
# ---------------------------------------------------------------------------

WHATIF_PATTERNS = [
    r"\bwhat if\b",
    r"\bif we (cut|reduce|increase|raise|lower)\b",
    r"\bhow much would.*(save|free up|cost)\b",
    r"\b(cut|reduce|lower|increase|raise)\b.*\b\d+(?:\.\d+)?\s*(?:%|percent\b)",
]

CATEGORY_ALIASES = {
    "hr": "Recruiting & HR",
    "recruitment": "Recruiting & HR",
    "food": "Meals & Entertainment",
    "meals": "Meals & Entertainment",
    "dining": "Meals & Entertainment",
    "payroll": "Salaries & Payroll",
    "salaries": "Salaries & Payroll",
    "rent": "Office Rent & Facilities",
    "travel": "Travel & Transportation",
    "transport": "Travel & Transportation",
    "software": "Software Subscriptions",
    "subscriptions": "Software Subscriptions",
    "cloud": "Cloud Services",
    "advertising": "Marketing & Advertising",
    "ads": "Marketing & Advertising",
    "insurance": "Insurance",
    "utilities": "Utilities",
    "equipment": "Equipment & Hardware",
    "hardware": "Equipment & Hardware",
    "consulting": "Professional Services",
}


def _category_from_alias(question: str, summary_pack: dict) -> Optional[str]:
    for alias, category in sorted(CATEGORY_ALIASES.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(alias)}\b", question, re.IGNORECASE):
            return category
    return None


def classify_question(question: str) -> str:
    q = question.lower()
    if any(re.search(p, q) for p in WHATIF_PATTERNS):
        return "whatif"
    return "general"


# ---------------------------------------------------------------------------
# Path 1: general questions answered from the summary pack
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_GENERAL = """You are a financial analyst assistant for a small startup.

You will be given a JSON context object built from several live endpoints.
Some fields cover the WHOLE YEAR, others cover only ONE MONTH — mixing
these up is the most common mistake, so read this key guide carefully:

WHOLE-YEAR fields (use these for "this year", "total", "overall", "annual"):
  - department_totals, category_totals: full-year totals
  - monthly_trend: full year, keyed by month
  - top_vendors_annual (if present): TRUE full-year vendor totals —
    always prefer this over "top_vendors" for any annual vendor question

ONE-MONTH-ONLY fields (these describe ONLY the "month" field's value,
usually the most recent month — do NOT use them to answer "this year"
questions):
  - by_department, by_category, budget_vs_actual, top_vendors

SPECIFIC-PAST-MONTH fields (present only if the question named a month):
  - budget_vs_actual_YYYY-MM: budget vs actual for that exact month,
    across all departments — use this to answer "was X over budget in
    <that month>" questions instead of escalating anywhere else

Rules you MUST follow:
- Only use numbers that appear in the context. Never invent, estimate,
  or calculate a number that isn't already there.
- Match the question's time scope to the right field using the guide
  above. If asked "this year" or "total", never substitute a
  single-month figure.
- State facts and the questions they raise. Do not give strategic advice
  or conclusions the data doesn't directly support (e.g. don't say
  "you should fire someone" — you can say "Engineering is your largest
  cost center at $X, more than Sales and Marketing combined").
- Be concise and concrete. Cite the specific number and time period.
- If, and only if, the context genuinely does not contain what's
  needed to answer (e.g. a specific expense line item, or a specific
  vendor/department/month combination not present anywhere above),
  respond with EXACTLY the single token: NEED_QUERY
  Do not add any other text when you do this.
"""


def answer_general_question(question: str, context: dict) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_GENERAL},
            {
                "role": "user",
                "content": (
                    f"Context:\n{json.dumps(context)}\n\n"
                    f"Question: {question}"
                ),
            },
        ],
        temperature=0.2,
    )
    answer = resp.choices[0].message.content.strip()
    return {
        "answer": answer,
        "type": "general",
        "needs_query": answer == "NEED_QUERY",
    }


# ---------------------------------------------------------------------------
# Path 2: what-if arithmetic — Python computes, LLM only phrases the result
# ---------------------------------------------------------------------------

def _find_category_or_vendor(question: str, summary_pack: dict):
    """Very simple keyword match against known categories/vendors.
    Good enough for v0; v1 can replace with embedding match like
    Role 1's categorizer."""
    q = question.lower()
    alias_category = _category_from_alias(question, summary_pack)
    if alias_category:
        return "category", alias_category
    for cat in summary_pack["categories"]:
        if cat.lower().split(" &")[0] in q or cat.lower() in q:
            return "category", cat
    for v in summary_pack.get("top_vendors_annual", summary_pack["top_vendors"]):
        if v["vendor"].lower() in q:
            return "vendor", v["vendor"]
    return None, None


def _find_percentage(question: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b)", question, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _named_dimensions(question: str, pack: dict) -> dict[str, str]:
    """Match non-overlapping names, including more than one ledger dimension."""
    q = question.lower()
    dimensions = {
        "department": pack["departments"],
        "category": pack["categories"],
        "vendor": [row["vendor"] for row in pack["top_vendors_annual"]],
    }
    matches = []
    for kind, names in dimensions.items():
        for name in names:
            for match in re.finditer(rf"(?<!\w){re.escape(name.lower())}(?!\w)", q):
                matches.append((match.start(), match.end(), kind, name))
    for alias, category in CATEGORY_ALIASES.items():
        for match in re.finditer(rf"\b{re.escape(alias)}\b", q):
            matches.append((match.start(), match.end(), "category", category))
    chosen, spans = {}, []
    for start, end, kind, name in sorted(matches, key=lambda item: (-(item[1] - item[0]), item[0])):
        if kind not in chosen and all(end <= left or start >= right for left, right in spans):
            chosen[kind] = name
            spans.append((start, end))
    return chosen


def _filtered_expenses(expenses, month: str | None = None, filters: dict[str, str] | None = None):
    scoped = expenses if month is None else expenses[expenses["month"] == month]
    for kind, name in (filters or {}).items():
        scoped = scoped[scoped[kind] == name]
    return scoped


def _scope_total(expenses, month: str | None, filters: dict[str, str] | None = None) -> tuple[float, int]:
    scoped = _filtered_expenses(expenses, month, filters)
    return round(float(scoped["amount"].sum()), 2), len(scoped)


def _ranked_totals(expenses, month: str | None, kind: str, filters: dict[str, str] | None = None) -> list[tuple[str, float]]:
    scoped = _filtered_expenses(expenses, month, {field: value for field, value in (filters or {}).items() if field != kind})
    totals = scoped.groupby(kind)["amount"].sum().sort_values(ascending=False)
    return [(str(name), round(float(value), 2)) for name, value in totals.items()]


def _list_limit(question: str) -> int:
    match = re.search(r"\b(?:top|bottom)\s+(\d{1,2})\b", question, re.IGNORECASE)
    return min(max(int(match.group(1)), 1), 10) if match else 1


def compute_whatif(question: str, summary_pack: dict) -> Optional[dict]:
    """Returns a structured arithmetic result, or None if we can't
    confidently parse the question — caller should fall back to refusal."""
    kind, target = _find_category_or_vendor(question, summary_pack)
    pct = _find_percentage(question)

    if kind is None or pct is None or pct < 0 or pct > 100:
        return None

    if kind == "category":
        annual_total = summary_pack["category_totals"].get(target)
    else:
        annual_total = next(
            (v["total"] for v in summary_pack.get("top_vendors_annual", summary_pack["top_vendors"]) if v["vendor"] == target),
            None,
        )

    if annual_total is None:
        return None

    savings = round(annual_total * (pct / 100), 2)
    direction = "increase" if re.search(r"\b(increase|raise|grow|higher|rise|more)\b|\bgo up\b", question, re.IGNORECASE) else "reduction"
    return {
        "target": target,
        "target_kind": kind,
        "percentage": pct,
        "annual_total": annual_total,
        "computed_change": savings,
        "direction": direction,
    }


def answer_whatif_question(question: str, summary_pack: dict) -> dict:
    result = compute_whatif(question, summary_pack)

    if result is None:
        return refuse(
            question,
            reason="I couldn't confidently match this to a specific category "
            "or vendor with a percentage in the summary pack.",
        )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You explain a pre-computed what-if calculation to a "
                    "founder in one or two plain-language sentences. "
                    "Do not recompute or second-guess the numbers you're given — "
                    "just phrase them clearly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Computed result (already correct, just phrase it): "
                    f"{json.dumps(result)}"
                ),
            },
        ],
        temperature=0.2,
    )
    return {
        "answer": resp.choices[0].message.content,
        "type": "whatif",
        "evidence": result,
    }


# ---------------------------------------------------------------------------
# Path 3: graceful refusal
# ---------------------------------------------------------------------------

def refuse(question: str, reason: str) -> dict:
    reason = reason.rstrip(". ") + "."
    return {
        "answer": (
            f"I can't answer that from the current data. {reason} "
            "Try a spending total, month comparison, top category or vendor, "
            "monthly average, spending share, or a percentage what-if."
        ),
        "type": "refusal",
    }


def answer_without_llm(question: str, pack: dict, expenses, budgets) -> dict:
    """Answer from one selected year's ledger and calculated aggregates."""
    from aggregates import budget_vs_actual

    q = question.lower()
    year = pack["year"]
    months = _mentioned_months(question, year)
    month = months[-1] if months else None
    trend = pack["monthly_trend"]
    year_label = str(year)
    filters = _named_dimensions(question, pack)
    target_kind, target_name = next(iter(filters.items()), (None, None))
    target_label = " and ".join(filters[kind] for kind in ("department", "category", "vendor") if kind in filters) if filters else None

    if re.search(r"\b(profit|revenue|income|forecast|predict)\b", q):
        return refuse(question, "The expense ledger has no revenue or forecast data.")

    if classify_question(question) == "whatif":
        result = compute_whatif(question, pack)
        if result is None:
            return refuse(question, "Name a known category or vendor and a percentage.")
        if month and month not in trend:
            return refuse(question, f"There are no confirmed expenses for {month}.")
        scenario_filters = {result["target_kind"]: result["target"], **filters}
        result["period_total"], _ = _scope_total(expenses, month, scenario_filters)
        if result["period_total"] == 0:
            return refuse(question, f"No spending is recorded for {target_label or result['target']} in {month or year}.")
        result["computed_change"] = round(result["period_total"] * result["percentage"] / 100, 2)
        result["filters"] = scenario_filters
        result["period"] = month or year_label
        direction = result["direction"]
        verb = "increase spending by" if direction == "increase" else "save"
        if direction == "reduction":
            result["computed_savings"] = result["computed_change"]
        return {
            "answer": (f"A {result['percentage']:g}% {direction} in {target_label or result['target']} "
                       f"would {verb} ${result['computed_change']:,.2f} in {result['period']}, "
                       f"based on recorded spending of ${result['period_total']:,.2f}. "
                       "This is a scenario, not a recorded result."),
            "type": "whatif", "evidence": result,
        }

    if "month" in q and any(word in q for word in ("highest", "biggest", "largest", "most", "lowest", "least", "smallest")):
        scoped = _filtered_expenses(expenses, filters=filters)
        if scoped.empty:
            return refuse(question, f"No {target_label or 'expense'} entries are recorded in {year}.")
        monthly = scoped.groupby("month")["amount"].sum().reindex(sorted(trend), fill_value=0)
        lowest = any(word in q for word in ("lowest", "least", "smallest"))
        chosen = monthly.idxmin() if lowest else monthly.idxmax()
        amount = round(float(monthly[chosen]), 2)
        label = f" for {target_label}" if target_label else ""
        return {"answer": f"{chosen} had the {'lowest' if lowest else 'highest'} recorded spending{label} in {year}: ${amount:,.2f}.",
                "type": "general", "evidence": {"month": chosen, "total": amount, "target": target_name}}

    if re.search(r"\b(average|mean)\b", q):
        if "monthly" in q or "per month" in q:
            scoped = _filtered_expenses(expenses, filters=filters)
            if scoped.empty:
                return refuse(question, f"No {target_label or 'expense'} entries are recorded in {year}.")
            monthly = scoped.groupby("month")["amount"].sum().reindex(sorted(trend), fill_value=0)
            value = round(float(monthly.mean()), 2)
            label = f" for {target_label}" if target_label else ""
            return {"answer": f"Average monthly spending{label} in {year} was ${value:,.2f} across {len(monthly)} recorded months.",
                    "type": "general", "evidence": {"average_monthly": value, "months": len(monthly)}}
        total, count = _scope_total(expenses, month, filters)
        if not count:
            return refuse(question, f"No matching expenses are recorded in {month or year}.")
        value = round(total / count, 2)
        return {"answer": f"The average recorded transaction{f' for {target_label}' if target_label else ''} in {month or year} was ${value:,.2f} across {count:,} transactions.",
                "type": "general", "evidence": {"average_transaction": value, "transactions": count}}

    if re.search(r"\b(how many|number of|count)\b", q) and re.search(r"\b(expenses|transactions|records|payments)\b", q):
        _, count = _scope_total(expenses, month, filters)
        return {"answer": f"There were {count:,} recorded transactions{f' for {target_label}' if target_label else ''} in {month or year}.",
                "type": "general", "evidence": {"transactions": count}}

    if re.search(r"\b(percentage|percent|share|portion|proportion)\s+of\b", q) and target_name:
        target_total, _ = _scope_total(expenses, month, filters)
        period_total, _ = _scope_total(expenses, month)
        share = round(target_total / period_total * 100, 1) if period_total else 0.0
        return {"answer": f"{target_label} made up {share:g}% of recorded spending in {month or year} (${target_total:,.2f} of ${period_total:,.2f}).",
                "type": "general", "evidence": {"target_total": target_total, "period_total": period_total, "share_pct": share}}

    dimension = ("category" if re.search(r"\bcategor(?:y|ies)\b", q) else
                 "department" if re.search(r"\bdepartments?\b", q) else
                 "vendor" if re.search(r"\bvendors?\b", q) else None)
    if dimension and "monthly" in q and not target_name:
        return refuse(question, f"Name a specific {dimension} for its monthly trend.")
    limit = _list_limit(question)
    if dimension and (limit > 1 or re.search(r"\b(breakdown|list|show)\b", q)):
        ranked = _ranked_totals(expenses, month, dimension, filters)
        if not ranked:
            return refuse(question, f"No expenses are recorded in {month or year}.")
        count = limit if limit > 1 else min(5, len(ranked))
        lines = "; ".join(f"{index}. {name}: ${amount:,.2f}" for index, (name, amount) in enumerate(ranked[:count], 1))
        plural = {"category": "categories", "department": "departments", "vendor": "vendors"}[dimension]
        context = f" within {target_label}" if target_label and target_kind != dimension else ""
        return {"answer": f"Top {min(count, len(ranked))} {plural} by spending in {month or year}{context}: {lines}.",
                "type": "general", "evidence": {"ranking": ranked[:count]}}

    if ("monthly" in q or "each month" in q) and re.search(r"\b(trend|breakdown|show|list|totals?)\b", q):
        scoped = _filtered_expenses(expenses, filters=filters)
        if scoped.empty:
            return refuse(question, f"No {target_label or 'expense'} entries are recorded in {year}.")
        monthly = scoped.groupby("month")["amount"].sum().reindex(sorted(trend), fill_value=0)
        values = "; ".join(f"{period}: ${float(value):,.2f}" for period, value in monthly.items())
        return {"answer": f"Monthly spending{f' for {target_label}' if target_label else ''} in {year}: {values}.", "type": "general"}

    comparison_terms = ("compare", "compared", "change", "difference", "increase", "decrease",
                        "rose", "fell", "grew", "dropped", "jumped", "between", "versus",
                        " vs ", "previous month", "month over month")
    if any(term in q for term in comparison_terms):
        if len(months) >= 2:
            earlier, later = (months[-2:] if re.search(r"\bfrom\b.*\bto\b", q) else sorted(months[-2:]))
        elif month:
            number = int(month[-2:])
            if number == 1:
                return refuse(question, "January has no previous month inside the selected calendar year.")
            earlier, later = f"{year}-{number - 1:02d}", month
        else:
            available = sorted(trend)
            if len(available) < 2:
                return refuse(question, f"There are fewer than two recorded months in {year}.")
            earlier, later = available[-2:]
        if earlier not in trend or later not in trend:
            return refuse(question, f"Both comparison months need confirmed expenses in {year}.")
        if target_name:
            before, _ = _scope_total(expenses, earlier, filters)
            after, _ = _scope_total(expenses, later, filters)
        else:
            before, after = trend[earlier], trend[later]
        change = round(after - before, 2)
        direction = "increased" if change > 0 else "decreased" if change < 0 else "stayed the same"
        percentage = round(abs(change) / before * 100, 1) if before else None
        suffix = f" ({percentage:g}%)." if percentage is not None else "; a percentage is undefined because the earlier total was zero."
        label = f"{target_label} spending" if target_label else "Spending"
        return {"answer": (f"{label} {direction} by ${abs(change):,.2f} from {earlier} "
                           f"(${before:,.2f}) to {later} (${after:,.2f}){suffix}"),
                "type": "comparison", "evidence": {"from_month": earlier, "to_month": later,
                "from_total": before, "to_total": after, "change": change, "change_pct": percentage,
                "target": target_name}}

    if month and re.search(r"\b(budget|over|under)\b", q):
        if budgets[budgets["month"] == month].empty:
            return refuse(question, f"There is no budget reference for {month}.")
        rows = budget_vs_actual(expenses, budgets, month)
        for row in rows:
            if row["department"].lower() in q:
                if row["budget"] == 0:
                    return refuse(question, f"There is no budget reference for {row['department']} in {month}.")
                status = "over" if row["variance"] > 0 else "under" if row["variance"] < 0 else "on"
                return {"answer": f"In {month}, {row['department']} was {status} budget: actual ${row['actual']:,.2f}, budget ${row['budget']:,.2f}, variance ${row['variance']:,.2f}.", "type": "general"}
        planned = sum(row["budget"] for row in rows)
        if planned:
            actual = sum(row["actual"] for row in rows)
            return {"answer": f"In {month}, recorded spend was ${actual:,.2f} against a budget of ${planned:,.2f}, a variance of ${actual - planned:+,.2f}.", "type": "general"}
        return refuse(question, f"There is no budget reference for {month}.")

    if len(filters) > 1:
        if month and month not in trend:
            return refuse(question, f"There are no confirmed expenses for {month}.")
        if not re.search(r"\b(spend|spent|expenses|total|payments|cost)\b", q):
            return refuse(question, "Ask for the spending total of the named department, category, or vendor.")
        amount, count = _scope_total(expenses, month, filters)
        return {"answer": f"Recorded spending for {target_label} in {month or year} was ${amount:,.2f} across {count:,} transactions.",
                "type": "general", "evidence": {"filters": filters, "total": amount, "transactions": count}}

    alias = _category_from_alias(question, pack)
    if alias:
        amount = (round(float(expenses[(expenses["month"] == month) & (expenses["category"] == alias)]["amount"].sum()), 2)
                  if month else pack["category_totals"].get(alias, 0.0))
        answer = (f"{alias} spending in {month or year_label} was ${amount:,.2f}." if amount
                  else f"No {alias} expenses were recorded in {month or year_label}.")
        return {"answer": answer, "type": "general"}

    ranking = any(word in q for word in ("biggest", "largest", "most", "top", "highest"))
    if ranking and "category" in q:
        totals = (expenses[expenses["month"] == month].groupby("category")["amount"].sum().to_dict()
                  if month else pack["category_totals"])
        if totals:
            name, amount = max(totals.items(), key=lambda item: item[1])
            return {"answer": f"{name} was the largest spending category in {month or year} at ${amount:,.2f}.", "type": "general"}
    if ranking and "department" in q:
        totals = (expenses[expenses["month"] == month].groupby("department")["amount"].sum().to_dict()
                  if month else pack["department_totals"])
        if totals:
            name, amount = max(totals.items(), key=lambda item: item[1])
            return {"answer": f"{name} had the highest department spend in {month or year} at ${amount:,.2f}.", "type": "general"}
    if ranking and "vendor" in q:
        if month:
            totals = expenses[expenses["month"] == month].groupby("vendor")["amount"].sum()
            if not totals.empty:
                name, amount = totals.idxmax(), float(totals.max())
                return {"answer": f"{name} was the top vendor in {month} at ${amount:,.2f}.", "type": "general"}
        else:
            row = pack["top_vendors_annual"][0]
            return {"answer": f"{row['vendor']} was the top vendor in {year} at ${row['total']:,.2f}.", "type": "general"}

    for kind, totals in (("department", pack["department_totals"]), ("category", pack["category_totals"])):
        for name, annual_amount in sorted(totals.items(), key=lambda item: len(item[0]), reverse=True):
            if name.lower() in q:
                amount = (round(float(expenses[(expenses["month"] == month) & (expenses[kind] == name)]["amount"].sum()), 2)
                          if month else annual_amount)
                return {"answer": f"{name} {kind} spending in {month or year_label} was ${amount:,.2f}.", "type": "general"}

    for row in pack["top_vendors_annual"]:
        if row["vendor"].lower() in q:
            amount = (round(float(expenses[(expenses["month"] == month) & (expenses["vendor"] == row["vendor"])]["amount"].sum()), 2)
                      if month else row["total"])
            return {"answer": f"Payments to {row['vendor']} in {month or year_label} totalled ${amount:,.2f}.", "type": "general"}

    if month and any(word in q for word in ("spend", "spent", "total", "expense", "expenditure")):
        total = trend.get(month)
        if total is not None:
            return {"answer": f"Total recorded spend in {month} was ${total:,.2f}.", "type": "general"}
        return refuse(question, f"There are no confirmed expenses for {month}.")

    if any(word in q for word in ("spend", "spent", "total", "expense", "expenditure")):
        total = round(float(expenses["amount"].sum()), 2)
        return {"answer": f"Total recorded expense spending in {year} was ${total:,.2f}.", "type": "general"}

    return refuse(question, "The local advisor can answer yearly or monthly spending, month comparisons, budgets, vendors, and percentage scenarios.")


# ---------------------------------------------------------------------------
# Entry point used by the FastAPI route
# ---------------------------------------------------------------------------

def answer_question(question: str, company_id: int = 1, selected_year: Optional[int] = None) -> dict:
    """company_id defaults to 1 for the single-company demo; wire this to
    the logged-in company's real id once auth (Function 1) is in place."""
    pack, expenses, budgets, year, available_years = _scoped_summary(question, selected_year)
    if pack is None:
        years = ", ".join(str(value) for value in available_years) or "none"
        return refuse(question, f"No confirmed expenses exist for {year or 'the requested year'}. Available years: {years}.")
    local_result = answer_without_llm(question, pack, expenses, budgets)
    if (local_result["type"] != "refusal" or not os.environ.get("GROQ_API_KEY")
            or re.search(r"\b(profit|revenue|income|forecast|predict)\b", question, re.IGNORECASE)):
        return local_result

    context = load_context(question, pack)
    try:
        result = answer_general_question(question, context)
    except Exception:
        return local_result

    # v0 -> v1 handoff: only escalate to a real database query when even
    # the enriched context (summary pack + annual vendors + any named
    # month's budget) genuinely couldn't answer it. This keeps things
    # fast and safe for the common case and only pays v1's cost — and
    # its DATABASE_URL dependency — when truly needed.
    if result.get("needs_query"):
        if not os.environ.get("DATABASE_URL"):
            return local_result
        from query_engine import answer_via_query_engine  # imported lazily so v0 works even without DATABASE_URL/psycopg2 configured
        return answer_via_query_engine(question, company_id)

    return result


if __name__ == "__main__":
    # quick manual smoke test — requires GROQ_API_KEY set
    for q in [
        "What was our biggest expense category this year?",
        "What if we cut Software Subscriptions by 20%?",
        "What will our revenue be next quarter?",
    ]:
        print("Q:", q)
        print(json.dumps(answer_question(q), indent=2))
        print()
