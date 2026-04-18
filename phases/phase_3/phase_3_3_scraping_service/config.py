"""
phases/phase_3_3_scraping_service/config.py
---------------------------------------------
All scraper configuration: corpus URLs, scheme metadata, HTTP settings,
and multi-strategy field selectors for Groww scheme pages.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Corpus: 5 Groww HDFC scheme URLs
# ---------------------------------------------------------------------------

GROWW_URLS: list[str] = [
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
]

# Static metadata per scheme slug (derived from URL path)
SCHEME_META: dict[str, dict[str, str]] = {
    "hdfc-large-cap-fund-direct-growth": {
        "scheme_name": "HDFC Large Cap Fund Direct Growth",
        "amc": "HDFC Mutual Fund",
        "category": "Large Cap",
    },
    "hdfc-equity-fund-direct-growth": {
        "scheme_name": "HDFC Equity Fund Direct Growth",
        "amc": "HDFC Mutual Fund",
        "category": "Flexi Cap",
    },
    "hdfc-elss-tax-saver-fund-direct-plan-growth": {
        "scheme_name": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
        "amc": "HDFC Mutual Fund",
        "category": "ELSS",
    },
    "hdfc-mid-cap-fund-direct-growth": {
        "scheme_name": "HDFC Mid-Cap Fund Direct Growth",
        "amc": "HDFC Mutual Fund",
        "category": "Mid Cap",
    },
    "hdfc-focused-fund-direct-growth": {
        "scheme_name": "HDFC Focused Fund Direct Growth",
        "amc": "HDFC Mutual Fund",
        "category": "Focused",
    },
}

# ---------------------------------------------------------------------------
# HTTP fetcher settings
# ---------------------------------------------------------------------------

HTTP_TIMEOUT_SECONDS: int = 15
HTTP_MAX_RETRIES: int = 3
HTTP_BACKOFF_SECONDS: list[int] = [2, 4, 8]   # delay before retry 1, 2, 3

HTTP_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # Note: Accept-Encoding is intentionally omitted — SSL-inspection proxies
    # can strip __NEXT_DATA__ when Brotli-compressed responses are tunnelled.
    # httpx handles identity/gzip decompression automatically.
}

WHITELISTED_DOMAIN: str = "groww.in"

# ---------------------------------------------------------------------------
# Field selectors
# Each field has an ordered list of strategies tried in sequence.
# Strategy types:
#   "data_attr"  -> tag[data-field="<value>"]
#   "css"        -> arbitrary CSS selector
#   "next_data"  -> key path inside window.__NEXT_DATA__ JSON (dot-separated)
#   "text_re"    -> regex on visible page text (last resort)
# ---------------------------------------------------------------------------

FIELD_SELECTORS: dict[str, list[dict[str, str]]] = {
    "scheme_name": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.scheme_name"},
        {"type": "css",       "value": "h1.schemeName"},
        {"type": "css",       "value": "h1[class*='scheme']"},
        {"type": "css",       "value": "h1[class*='fund']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.schemeName"},
        {"type": "next_data", "value": "props.pageProps.fundData.schemeName"},
        {"type": "css",       "value": "title"},
    ],
    "nav": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.nav"},
        {"type": "data_attr", "value": "nav"},
        {"type": "css",       "value": "[class*='navValue']"},
        {"type": "css",       "value": "[class*='nav__value']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.nav"},
        {"type": "text_re",   "value": r"NAV[:\s₹]+([0-9,]+\.?[0-9]*)"},
    ],
    "expense_ratio": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.expense_ratio"},
        {"type": "data_attr", "value": "expenseRatio"},
        {"type": "css",       "value": "[class*='expenseRatio']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.expenseRatio"},
        {"type": "next_data", "value": "props.pageProps.fundData.ter"},
        {"type": "text_re",   "value": r"[Ee]xpense [Rr]atio[:\s]+([0-9.]+\s*%)"},
    ],
    "exit_load": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.exit_load"},
        {"type": "data_attr", "value": "exitLoad"},
        {"type": "css",       "value": "[class*='exitLoad']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.exitLoad"},
        {"type": "text_re",   "value": r"[Ee]xit [Ll]oad[:\s]+(.+?)(?:\n|$)"},
    ],
    "min_sip": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.min_sip_investment"},
        {"type": "data_attr", "value": "minSipAmount"},
        {"type": "css",       "value": "[class*='minSip']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.minSipAmount"},
        {"type": "next_data", "value": "props.pageProps.fundData.sipMinAmount"},
        {"type": "text_re",   "value": r"[Mm]in(?:imum)?\s+SIP[:\s₹]+([0-9,]+)"},
    ],
    "min_lumpsum": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.min_investment_amount"},
        {"type": "data_attr", "value": "minLumpsum"},
        {"type": "css",       "value": "[class*='minLumpsum']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.minLumpsumAmount"},
        {"type": "next_data", "value": "props.pageProps.fundData.lumpsumMinAmount"},
        {"type": "text_re",   "value": r"[Mm]in(?:imum)?\s+[Ll]umpsum[:\s₹]+([0-9,]+)"},
    ],
    "riskometer": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.nfo_risk"},
        {"type": "data_attr", "value": "riskLevel"},
        {"type": "css",       "value": "[class*='riskometer']"},
        {"type": "css",       "value": "[class*='riskLevel']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.riskLevel"},
        {"type": "text_re",   "value": r"[Rr]isk(?:ometer)?[:\s]+(Very High|High|Moderately High|Moderate|Moderately Low|Low)"},
    ],
    "benchmark": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.benchmark_name"},
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.benchmark"},
        {"type": "data_attr", "value": "benchmark"},
        {"type": "css",       "value": "[class*='benchmark']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.benchmark"},
        {"type": "text_re",   "value": r"[Bb]enchmark[:\s]+(.+?)(?:\n|$)"},
    ],
    "fund_manager": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.fund_manager_details"},
        {"type": "next_data", "value": "props.pageProps.schemeData.fundManagers"},
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.fund_manager"},
        {"type": "data_attr", "value": "fundManager"},
        {"type": "css",       "value": "[class*='fundManager']"},
        {"type": "css",       "value": "[class*='managerName']"},
        {"type": "text_re",   "value": r"[Ff]und [Mm]anager[:\s]+(.+?)(?:\n|$)"},
    ],
    "aum": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.aum"},
        {"type": "data_attr", "value": "aum"},
        {"type": "css",       "value": "[class*='aum']"},
        {"type": "css",       "value": "[class*='fundSize']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.aum"},
        {"type": "next_data", "value": "props.pageProps.schemeData.fundSize"},
        {"type": "text_re",   "value": r"(?:AUM|Fund\s+Size)[:\s₹]+([0-9,]+\.?[0-9]*\s*(?:Cr|crore|L\s*Cr))"},
    ],
    # Groww star rating (1–5)
    "rating": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.groww_rating"},
        {"type": "data_attr", "value": "rating"},
        {"type": "css",       "value": "[class*='starRating']"},
        {"type": "css",       "value": "[class*='gwRating']"},
        {"type": "css",       "value": "[aria-label*='rating']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.rating"},
        {"type": "next_data", "value": "props.pageProps.schemeData.growwRating"},
        {"type": "text_re",   "value": r"(?:Rating|Stars?)[:\s]+([1-5](?:\.[0-9])?\s*(?:star|\/5)?)"},
    ],
    "fund_house": [
        {"type": "next_data", "value": "props.pageProps.mfServerSideData.fund_house"},
        {"type": "data_attr", "value": "fundHouse"},
        {"type": "css",       "value": "[class*='fundHouse']"},
        {"type": "css",       "value": "[class*='amcName']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.fundHouse"},
    ],
    # ELSS-only fields
    "lock_in": [
        {"type": "data_attr", "value": "lockIn"},
        {"type": "css",       "value": "[class*='lockIn']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.lockIn"},
        {"type": "text_re",   "value": r"[Ll]ock.?[Ii]n[:\s]+(.+?)(?:\n|$)"},
    ],
    "tax_benefit": [
        {"type": "css",       "value": "[class*='taxBenefit']"},
        {"type": "next_data", "value": "props.pageProps.schemeData.taxBenefit"},
        {"type": "text_re",   "value": r"80C|[Tt]ax [Bb]enefit[:\s]+(.+?)(?:\n|$)"},
    ],
}

# Fields to extract for ELSS schemes only
ELSS_ONLY_FIELDS: list[str] = ["lock_in", "tax_benefit"]

# ---------------------------------------------------------------------------
# Core fields — the 5 primary data points required per scheme.
# These drive the FAQ answers and are always extracted and stored.
# ---------------------------------------------------------------------------
CORE_FIELDS: list[str] = [
    "nav",           # Net Asset Value  (updated daily)
    "min_sip",       # Minimum SIP amount
    "aum",           # Fund Size (Assets Under Management)
    "expense_ratio", # Total Expense Ratio
    "rating",        # Groww star rating (CRISIL / Value Research sourced)
]

# Supporting fields — extracted alongside core fields for richer answers
SUPPORTING_FIELDS: list[str] = [
    "exit_load",
    "min_lumpsum",
    "riskometer",
    "benchmark",
    "fund_manager",
    "fund_house",
]

# All fields extracted for every scheme (core + supporting)
STANDARD_FIELDS: list[str] = ["scheme_name"] + CORE_FIELDS + SUPPORTING_FIELDS

# Output paths (relative to project root — scripts are run from there)
SCRAPER_OUTPUT_DIR: str = "scraper/output"
SNAPSHOTS_DIR: str = "scraper/snapshots"
