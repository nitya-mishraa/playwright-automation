#!/usr/bin/env python3
"""
score_bids.py — Local LLM Tender Intelligence Scoring

Reads every awarded/technical/financial _summary.json in results/,
sends each unscored bid to a local llama.cpp server (llama-server) together
with the Company Profile, and appends relevance_score, matching_capabilities,
missing_capabilities, and recommendation back into the JSON file without
overwriting existing fields.

Requirements:
  pip install requests
  A running llama.cpp server, e.g.:
    llama-server -m Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8080

  NOTE: SmolVLM-500M-Instruct is a vision-language model (500M text backbone,
  needs an mmproj file for image input). It is not a good fit for this
  text-only reasoning/structured-JSON task and will likely produce
  unreliable scores. Prefer a small text-instruct GGUF model instead, e.g.
  Qwen2.5-3B-Instruct-GGUF (good JSON adherence, runs fine on CPU).

Usage:
  python score_bids.py                                # score all unscored bids
  python score_bids.py --url http://localhost:8080    # llama-server base URL
  python score_bids.py --rescore                       # re-score already-scored bids
  python score_bids.py --keyword AI                    # only process one keyword folder
  python score_bids.py --dry-run                       # preview prompts, no writes
"""

import argparse
import json
import os
import re
import sys
import time

import requests

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR  = os.path.join(SCRIPT_DIR, 'results')
PROFILE_PATH = os.path.join(SCRIPT_DIR, 'company_profile.json')
LLAMACPP_URL = 'http://localhost:8080'
CATEGORIES   = ['awarded', 'technical', 'financial']

DEFAULT_PROFILE = {
    "company_name": "EarthSense Labs",
    "description": (
        "A deep-tech company specialising in earth observation, geospatial intelligence, "
        "remote sensing, satellite data analytics, GIS solutions, AI-powered surveillance, "
        "and disaster management technology for defence and government clients."
    ),
    "core_capabilities": [
        "Satellite imagery analysis and remote sensing",
        "AI/ML for geospatial and earth observation data",
        "GIS mapping, analytics, and digital twin solutions",
        "Drone-based surveillance and aerial reconnaissance",
        "Flood detection and early warning systems",
        "Disaster management monitoring and response technology",
        "Cybersecurity for critical and defence infrastructure",
        "Intelligence and surveillance system integration",
        "Analytics dashboards and decision support platforms",
        "Computer vision for aerial and satellite imagery",
        "Change detection and environmental monitoring",
        "Hyperspectral and multispectral data processing",
    ],
    "target_sectors": [
        "Defence and national security",
        "Disaster management and emergency response",
        "Urban planning and smart cities",
        "Agriculture and crop monitoring",
        "Environmental and forest monitoring",
        "Border surveillance and perimeter security",
    ],
    "experience": "Government and defence sector technology projects in India",
}


# ── Capability taxonomy (drives deterministic scoring — NOT the LLM) ──────────
#
# Every phrase here is tied to one of company_profile.json's core_capabilities.
# matching_capabilities in the final output is restricted to this whitelist —
# a tender only "matches" if its own text contains a phrase that genuinely
# signals that capability. The LLM never gets to invent entries from the bid
# text itself.

CAPABILITY_KEYWORDS = {
    "Satellite imagery analysis and remote sensing": [
        r"satellite imagery", r"remote sensing", r"satellite data",
        r"satellite mapping", r"earth observation imagery", r"satellite-based monitoring",
    ],
    "AI/ML for geospatial and earth observation data": [
        r"artificial intelligence", r"machine learning", r"deep learning",
        r"geospatial ai", r"earth observation data",
    ],
    "GIS mapping, analytics, and digital twin solutions": [
        r"geographic information system",
        r"\bgis\b[\w\s/,.-]{0,25}(survey|mapping|data|software|based|analysis|application|solution)",
        r"(survey|mapping)[\w\s/,.-]{0,25}\bgis\b",
        r"digital twin", r"spatial analytics", r"geo[- ]referenc",
    ],
    "Drone-based surveillance and aerial reconnaissance": [
        r"\bdrone\b", r"\buav\b", r"unmanned aerial", r"aerial surveillance",
        r"aerial reconnaissance", r"\brpav\b", r"quadcopter",
    ],
    "Flood detection and early warning systems": [
        r"flood detection", r"flood forecast", r"flood monitoring", r"early warning system",
    ],
    "Disaster management monitoring and response technology": [
        r"disaster management", r"disaster risk", r"disaster response", r"calamity monitoring",
    ],
    "Cybersecurity for critical and defence infrastructure": [
        r"cyber ?security", r"cyber resilience", r"information security audit",
        r"\bvapt\b", r"critical infrastructure protection",
    ],
    "Intelligence and surveillance system integration": [
        r"surveillance system", r"security surveillance", r"video analytics",
        r"cctv analytics", r"\bisr\b", r"border surveillance", r"intelligence system",
    ],
    "Analytics dashboards and decision support platforms": [
        r"analytics dashboard", r"decision support system",
        r"business intelligence dashboard", r"data visuali[sz]ation platform",
    ],
    "Computer vision for aerial and satellite imagery": [
        r"computer vision", r"object detection", r"image recognition",
        r"(aerial|satellite) imagery (analysis|processing)",
    ],
    "Change detection and environmental monitoring": [
        r"change detection", r"environmental monitoring", r"land use monitoring",
        r"encroachment detection", r"deforestation monitoring",
    ],
    "Hyperspectral and multispectral data processing": [
        r"hyperspectral", r"multispectral",
    ],
}

# Bare "gis"/"ai" style phrases can false-positive against unrelated GeM
# categories (e.g. "GIS SS" = Gas Insulated Switchgear Sub-Station, an
# electrical-infra tender that has nothing to do with Geographic Information
# Systems). If these markers are present, don't credit a bare GIS match.
_GIS_ELECTRICAL_EXCLUDE = re.compile(r"\d+\s*kv\b|switchgear|substation", re.I)

# Generic GeM commodity/service categories that recur across every keyword
# folder (because the scraper matches on loose keyword hits) but have no
# relation to EarthSense Labs' AI / GIS / remote sensing / drone / surveillance
# / analytics domain. Any hit here actively drags the score down.
UNRELATED_DOMAIN_KEYWORDS = [
    r"\btransport(ation)?\b", r"\blogistics\b", r"earth moving equipment",
    r"material handling equipment", r"crane hiring",
    r"vehicle hiring", r"hiring of (a )?vehicle", r"car hiring", r"bus hiring",
    r"cab (and|&) taxi", r"taxi hiring", r"\bcourier\b",
    r"\brepair(ing)?\b", r"\boverhaul(ing)?\b", r"\bmaintenance\b", r"\bamc\b", r"\bcmc\b",
    r"\bhousekeeping\b", r"cleaning service", r"pest control", r"horticulture", r"\bgardening\b",
    r"manpower (outsourcing|supply)", r"security guard service", r"facility management",
    r"catering service", r"canteen service",
    r"\btentage\b", r"tent rental", r"\bfurniture\b", r"\bstationery\b",
    r"printing service", r"civil work", r"construction work", r"electrical work",
    r"fuel supply", r"diesel supply", r"petrol supply", r"lubricant supply",
    r"generator set", r"\bdg set\b",
    r"insurance service", r"vocational training", r"social media agency",
    r"educational lab", r"school development",
]

MATCH_POINTS      = 20   # score contributed per genuine capability match
UNRELATED_PENALTY = 25   # score deducted per unrelated-domain hit


def find_genuine_matches(company_profile, text):
    """Return the subset of company_profile's core_capabilities whose keywords
    actually appear in the tender text. This is the ONLY source of truth for
    matching_capabilities — never the bid text itself."""
    whitelist = set(company_profile.get('core_capabilities', []))
    text_l = text.lower()
    matches = []
    for capability, patterns in CAPABILITY_KEYWORDS.items():
        if capability not in whitelist:
            continue
        for pat in patterns:
            if re.search(pat, text_l):
                if 'gis' in pat and _GIS_ELECTRICAL_EXCLUDE.search(text_l):
                    continue
                matches.append(capability)
                break
    return matches


def find_unrelated_hits(text):
    text_l = text.lower()
    return [pat for pat in UNRELATED_DOMAIN_KEYWORDS if re.search(pat, text_l)]


def compute_final_score(llm_score, genuine_matches, unrelated_hits):
    """Blend the LLM's contextual score with a deterministic keyword-overlap
    signal, then apply an unrelated-domain penalty. Guarantees that a bid with
    zero genuine capability overlap can never score high, no matter what the
    LLM said, and that unrelated domains (transport, logistics, vehicle
    hiring, repair/maintenance, etc.) are actively penalised."""
    overlap_score = min(len(genuine_matches) * MATCH_POINTS, 100)
    penalty = min(len(unrelated_hits) * UNRELATED_PENALTY, 100)

    if genuine_matches:
        base = round(0.5 * llm_score + 0.5 * overlap_score)
    else:
        base = min(llm_score, 15)

    return max(0, min(100, base - penalty))


def deterministic_fallback_score(genuine_matches, unrelated_hits):
    """Used when the LLM call fails/times out/returns invalid JSON — score
    from keyword overlap alone so every bid still gets a corrected,
    consistent result instead of retaining stale pre-fix data."""
    overlap_score = min(len(genuine_matches) * MATCH_POINTS, 100) if genuine_matches else 0
    penalty = min(len(unrelated_hits) * UNRELATED_PENALTY, 100)
    return max(0, min(100, overlap_score - penalty))


def build_recommendation(final_score, genuine_matches, unrelated_hits):
    if final_score >= 85:
        reason = f"strong genuine overlap with {', '.join(genuine_matches[:2])}"
        return f"Pursue — {reason}."
    if final_score >= 70:
        if genuine_matches:
            reason = f"genuine overlap with {', '.join(genuine_matches[:2])}"
        else:
            reason = "solid sector/ministry alignment with the company's focus areas"
        return f"Relevant — {reason}."
    if final_score >= 40:
        if genuine_matches:
            reason = f"partial overlap with {', '.join(genuine_matches[:2])}, but much of the scope is generic"
        else:
            reason = "sector/ministry alignment exists but no direct capability match was found"
        return f"Consider — {reason}."
    if unrelated_hits:
        reason = ("this is a generic non-technical category (transport / logistics / vehicle hiring / "
                  "repair & maintenance / similar) outside EarthSense Labs' AI, GIS, remote sensing, "
                  "drone and surveillance focus")
    else:
        reason = "no genuine overlap with EarthSense Labs' core capabilities"
    return f"Skip — {reason}."


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_company_profile():
    if not os.path.exists(PROFILE_PATH):
        print(f"[WARN] company_profile.json not found — using built-in default.")
        return DEFAULT_PROFILE
    with open(PROFILE_PATH, encoding='utf-8') as f:
        return json.load(f)


def build_prompt(company_profile, bid):
    items  = bid.get('items', '') or ''
    bid_no = bid.get('bid_no', '')
    status = bid.get('status', '')

    listing_lines = bid.get('listing', [])
    listing_text  = '\n'.join(listing_lines) if listing_lines else ''

    # Pull nested bid_details / buyer_details from results[]
    bid_details   = {}
    buyer_details = {}
    for res in bid.get('results', []):
        d = res.get('data') or {}
        if not bid_details  and d.get('bid_details'):
            bid_details  = d['bid_details']
        if not buyer_details and d.get('buyer_details'):
            buyer_details = d['buyer_details']

    ministry   = buyer_details.get('ministry', '')   or ''
    department = buyer_details.get('department', '') or ''
    org        = buyer_details.get('organisation', '') or ''
    validity   = bid_details.get('bid_validity_days', '') or ''

    company_json = json.dumps(company_profile, indent=2, ensure_ascii=False)
    capability_list = '\n'.join(f'  {i}. {c}' for i, c in enumerate(company_profile.get('core_capabilities', []), 1))

    return f"""You are a senior government tender analyst. Your task is to evaluate how relevant the tender below is for the company described, based STRICTLY on genuine capability and sector overlap — not on surface keyword collisions.

COMPANY PROFILE:
{company_json}

The company's ONLY real capabilities are this exact whitelist — nothing else:
{capability_list}

TENDER INFORMATION:
- Bid Number  : {bid_no}
- Status      : {status}
- Items/Scope : {items}
- Ministry    : {ministry}
- Department  : {department}
- Organisation: {org}
- Validity    : {validity} days
- Listing:
{listing_text}

CRITICAL RULES:
1. This company does NOT do transport, logistics, vehicle/equipment hiring, repair, maintenance, AMC/CMC contracts, housekeeping, manpower supply, catering, construction, or any other generic commodity/service work — even if the tender happens to mention "systems", "equipment", or contains one of the company's keywords in an unrelated context (e.g. "GIS SS" in an electrical-substation tender is NOT Geographic Information Systems). Score these near 0 regardless of how the items are phrased.
2. "matching_capabilities" MUST contain ONLY exact strings copied verbatim from the whitelist above. NEVER copy or paraphrase words from the tender's Items/Scope or Listing text into this field. If nothing from the whitelist genuinely applies, return an empty array.
3. A high score requires the tender's actual technical requirement — not just a ministry or sector name — to genuinely need one or more of the whitelisted capabilities.

Return ONLY a JSON object with EXACTLY these four keys (no markdown, no extra text):
{{
  "relevance_score": <integer 0-100, where 0=completely irrelevant, 100=perfect match>,
  "matching_capabilities": [<array of strings — ONLY exact entries from the whitelist above, never text from the tender>],
  "missing_capabilities": [<array of strings — what the company lacks for this tender; empty array if none>],
  "recommendation": "<one concise sentence starting with Pursue / Relevant / Consider / Skip and explaining the key reason>"
}}"""


def call_llamacpp(prompt, base_url):
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    url = base_url.rstrip('/') + '/v1/chat/completions'
    try:
        resp = requests.post(url, json=payload, timeout=240)
        resp.raise_for_status()
        data    = resp.json()
        content = data['choices'][0]['message']['content']
        return json.loads(content)
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Cannot connect to llama.cpp server at {base_url}")
        print("        Start it first, e.g.:")
        print("        llama-server -m Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8080")
        sys.exit(1)
    except requests.exceptions.HTTPError as exc:
        body = getattr(exc.response, 'text', '')[:400]
        print(f"\n[ERROR] llama.cpp server HTTP {exc.response.status_code}: {body}")
        sys.exit(1)
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        print(f"  [WARN] LLM returned unexpected/non-JSON content: {exc}")
        return None


def validate(score_data):
    if not isinstance(score_data, dict):
        return False
    score = score_data.get('relevance_score')
    if not isinstance(score, (int, float)):
        return False
    if not (0 <= float(score) <= 100):
        return False
    if not isinstance(score_data.get('matching_capabilities'), list):
        return False
    if not isinstance(score_data.get('missing_capabilities'), list):
        return False
    if not isinstance(score_data.get('recommendation'), str):
        return False
    return True


# ── Core processing ───────────────────────────────────────────────────────────

def process_file(fp, company_profile, base_url, rescore=False, dry_run=False):
    """Score all unscored bids in a single summary JSON file. Returns count changed."""
    with open(fp, encoding='utf-8') as f:
        bids = json.load(f)
    if not isinstance(bids, list):
        return 0

    changed = 0
    for i, bid in enumerate(bids):
        if not rescore and 'relevance_score' in bid:
            continue

        bid_no = bid.get('bid_no', f'entry-{i}')
        print(f"    Scoring {bid_no} ...", end=' ', flush=True)

        prompt = build_prompt(company_profile, bid)

        if dry_run:
            print("[DRY-RUN — skipped LLM call]")
            print("    --- PROMPT PREVIEW ---")
            print(prompt[:600])
            print("    ...")
            continue

        result = call_llamacpp(prompt, base_url)

        # genuine_matches/unrelated_hits are computed from company_profile.json
        # vs. the bid text regardless of what the LLM returns — they are the
        # ONLY source for matching_capabilities and are always applied, so a
        # flaky/timed-out LLM call can never leave a bid with stale, bid-text-
        # derived "matching capabilities" or an unvetted score.
        listing_text = '\n'.join(bid.get('listing', []) or [])
        bid_text = f"{bid.get('items', '') or ''}\n{listing_text}"
        genuine_matches = find_genuine_matches(company_profile, bid_text)
        unrelated_hits  = find_unrelated_hits(bid_text)

        if result and validate(result):
            llm_score      = float(result['relevance_score'])
            final_score    = compute_final_score(llm_score, genuine_matches, unrelated_hits)
            missing_caps   = [str(c) for c in result['missing_capabilities']]
            llm_note       = f"llm={int(llm_score)}"
        else:
            final_score  = deterministic_fallback_score(genuine_matches, unrelated_hits)
            missing_caps = []
            llm_note     = "llm=unavailable"

        bid['relevance_score']       = final_score
        bid['matching_capabilities'] = genuine_matches
        bid['missing_capabilities']  = missing_caps
        bid['recommendation']        = build_recommendation(final_score, genuine_matches, unrelated_hits)
        changed += 1
        label = ('Pursue' if final_score >= 85 else
                  'Relevant' if final_score >= 70 else
                  'Consider' if final_score >= 40 else 'Skip')
        print(f"score={final_score}  [{label}]  ({llm_note}, matches={len(genuine_matches)}, unrelated={len(unrelated_hits)})")

        # Save after every bid (not just at the end of the file) so a killed/
        # interrupted process loses at most one bid's work, not the whole file.
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(bids, f, indent=2, ensure_ascii=False)

        time.sleep(0.05)

    if changed and not dry_run:
        print(f"    Saved {fp}")

    return changed


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Score GeM tender bids using a local llama.cpp server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--url', default=LLAMACPP_URL,
                        help=f'llama.cpp server base URL (default: {LLAMACPP_URL})')
    parser.add_argument('--rescore', action='store_true',
                        help='Re-score bids that already have a relevance_score')
    parser.add_argument('--keyword', default=None,
                        help='Only process a specific keyword folder (e.g. AI)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print prompts without calling the LLM or writing files')
    args = parser.parse_args()

    company_profile = load_company_profile()

    print('\n' + '=' * 60)
    print(f"  GeM Tender Intelligence Scorer")
    print(f"  Company : {company_profile.get('company_name', 'Unknown')}")
    print(f"  Server  : {args.url}")
    print(f"  Rescore : {args.rescore}")
    print(f"  Dry-run : {args.dry_run}")
    print('=' * 60)

    if not os.path.isdir(RESULTS_DIR):
        print(f"\n[ERROR] Results directory not found: {RESULTS_DIR}")
        sys.exit(1)

    keywords = sorted(
        d for d in os.listdir(RESULTS_DIR)
        if os.path.isdir(os.path.join(RESULTS_DIR, d))
    )
    if args.keyword:
        if args.keyword not in keywords:
            print(f"[ERROR] Keyword folder '{args.keyword}' not found in {RESULTS_DIR}")
            print(f"        Available: {', '.join(keywords)}")
            sys.exit(1)
        keywords = [args.keyword]

    total_scored = 0
    for kw in keywords:
        kw_dir = os.path.join(RESULTS_DIR, kw)
        for cat in CATEGORIES:
            fp = os.path.join(kw_dir, f'{cat}_summary.json')
            if not os.path.exists(fp):
                continue
            print(f"\n[{kw} / {cat}]")
            n = process_file(fp, company_profile, args.url,
                             rescore=args.rescore, dry_run=args.dry_run)
            total_scored += n

    print(f"\n{'=' * 60}")
    print(f"  Done — {total_scored} bid(s) scored / updated.")
    print(f"  Restart the dashboard to see updated scores.")
    print('=' * 60 + '\n')


if __name__ == '__main__':
    main()
