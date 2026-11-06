"""Split 'compound' cells (several numbers in one cell) into low / high, by rule. Nothing printed is changed.
Usage: python3 split_compound.py out/observations_v2.json db/printed_prices_v2.csv db/printed_prices_v3.csv
Adds columns: split_rule, split_confidence, split_note, price_low_parts, price_high_parts, price_low_derived, price_high_derived, derived_unit
Derived values are arithmetic inside ONE currency system (s/d -> pence, dollars+cents -> dollars); no currency conversion.
"""
import csv, json, re, sys, collections
obs_path, v2_path, out_path = sys.argv[1:4]
obs = {(o["block_uid"], str(o["row_no"]), o["market_place"] or ""): o for o in json.load(open(obs_path))}
TOK = re.compile(r"\d+\s*\d?/\d+|\d+")
def val(t):
    m = re.match(r"^(\d+)\s*(\d)/(\d+)$", t)
    if m: return int(m[1]) + int(m[2]) / int(m[3])
    m = re.match(r"^(\d)/(\d+)$", t)
    return int(m[1]) / int(m[2]) if m else float(t)
def fmt(x): return str(int(x)) if x == int(x) else str(x)

def split(T, cur):
    n = len(T)
    if n == 2:
        lo, hi = T
        plausible_range = lo > 0 and lo <= hi and hi / lo <= 3
        if plausible_range and not (cur == "dollars" and lo == int(lo) and hi < 100 and hi >= 10 and hi / lo > 3):
            return dict(rule="two_numbers_low_high", conf="medium", low=[lo], high=[hi], du="as_printed_unit", dl=lo, dh=hi), ""
        # not a believable low-high pair: read it as ONE price = unit + subunit
        if lo != int(lo): return None, "n2_first_number_fractional"
        if cur == "lsd":
            if hi < 12: return dict(rule="shillings_pence_single", conf="medium", low=[lo, hi], high=None, du="pence", dl=lo * 12 + hi, dh=None), ""
            return None, "n2_lsd_not_shillings_pence"
        if hi < 100:
            return dict(rule="dollars_cents_single", conf="medium" if cur == "dollars" else "low", low=[lo, hi], high=None, du="dollars", dl=lo + hi / 100, dh=None), ""
        return None, "n2_unresolved"
    if n == 6:
        a, b = T[:3], T[3:]
        ok = all(x[1] < 20 and x[2] < 12 for x in (a, b))
        hi_zero = b == [0, 0, 0]
        if not ok: return None, "n6_not_lsd_shaped"
        pence = lambda x: x[0] * 240 + x[1] * 12 + x[2]
        if not hi_zero and pence(b) < pence(a): return None, "n6_high_lower_than_low"
        return dict(rule="lsd_six_numbers", conf="high", low=a, high=None if hi_zero else b, du="pence",
                    dl=pence(a), dh=None if hi_zero else pence(b)), ""
    if n == 4:
        (a, b), (c, d) = T[:2], T[2:]
        sd = b < 12 and d < 12 and a < 20 and c < 20
        dc = b >= 10 and d >= 10 and b < 100 and d < 100
        if cur == "lsd" and sd: kind = "sd"
        elif cur == "dollars" and dc: kind = "dc"
        elif cur == "unknown" and sd and not dc: kind = "sd"
        elif cur == "unknown" and dc and not sd: kind = "dc"
        else: return None, "n4_pair_type_ambiguous"
        if kind == "sd":
            lo, hi = a * 12 + b, c * 12 + d
            if hi < lo: return None, "n4_high_lower_than_low"
            return dict(rule="shillings_pence_pairs", conf="medium", low=[a, b], high=[c, d], du="pence", dl=lo, dh=hi), ""
        lo, hi = a + b / 100, c + d / 100
        if hi < lo: return None, "n4_high_lower_than_low"
        return dict(rule="dollars_cents_pairs", conf="medium", low=[a, b], high=[c, d], du="dollars", dl=lo, dh=hi), ""
    if n == 3: return None, "n3_ambiguous_one_column_empty"   # 4-column s/d tables leave a column blank: only the image can say which
    return None, f"n{n}_ambiguous"

ALLOWED_WORDS = {"cash", "scarce", "none", "nominal", "dull", "plenty", "demand", "about", "bush", "bushel", "barrel", "gallon", "hhds", "ditto", "pound", "quintal", "pipe", "ton"}
MARK_SD = re.compile(r"(\d+)\s*s\b\.?\s*(?:&|and)?\s*(\d+(?:\s*\d[/-]\d)?)\s*d\b", re.I)
MARK_S = re.compile(r"(\d+)\s*s\b", re.I)
MARK_PENCE_FRAC = re.compile(r"(\d+)\s*d\.?\s+(\d)[-/](\d)\b", re.I)    # '7d 1-2' = 7 1/2 pence
rows = list(csv.DictReader(open(v2_path, encoding="utf-8")))
DC_BLOCKS = {x["block_uid"] for x in rows if re.search(r"\d\s*c\b", x["price_low_as_printed"] + " " + x["price_high_as_printed"])}
new = ["split_rule", "split_confidence", "split_note", "price_low_parts", "price_high_parts", "price_low_derived", "price_high_derived", "derived_unit"]
cnt = collections.Counter()
for r in rows:
    for c in new: r[c] = ""
    o = obs.get((r["block_uid"], r["row_no"], r["market_place"]), {})
    s = (o.get("suspect_fields") or {}).get("price_low", "")
    if not s.startswith("compound_number:"): continue
    T = [val(t.replace(" ", " ")) for t in TOK.findall(s.split(":", 1)[1])]
    low_txt, high_txt = r["price_low_as_printed"], r["price_high_as_printed"]
    res = None; why = ""
    # guard 1: words from a neighbouring column sit inside the price cell -> do not guess
    bad_words = [w for w in re.findall(r"[A-Za-z]{4,}", low_txt + " " + high_txt) if w.lower() not in ALLOWED_WORDS]
    if bad_words:
        r["split_rule"], r["split_note"] = "unresolved", "text_in_price_cell:" + bad_words[0]; cnt["unresolved:text_in_price_cell"] += 1; continue
    # guard 2: a pence mark with no readable shilling mark (e.g. '38 9d' may be '3s 9d') -> do not guess
    # rule A: explicit marks decide  ('6s 6d', '22s. & 6d.')
    # rule 0: tables written "1d 67c" = 1 DOLLAR 67 CENTS (d = dollars, c = cents), recognised table-wide
    if r["block_uid"] in DC_BLOCKS:
        amts = []
        for m in re.finditer(r"(\d+)\s*d\b(?:\s*(\d+)\s*c\b)?", low_txt + " " + high_txt):
            amts.append((int(m[1]), int(m[2]) if m[2] else 0))
        if amts:
            res = dict(rule="marked_dollars_cents", conf="high", low=list(amts[0]), high=list(amts[1]) if len(amts) > 1 else None, du="dollars",
                       dl=amts[0][0] + amts[0][1] / 100, dh=(amts[1][0] + amts[1][1] / 100) if len(amts) > 1 else None)
            if res["dh"] is not None and res["dh"] < res["dl"]: res = None
    mk = MARK_SD.search(low_txt) if res is None else None
    mp = MARK_PENCE_FRAC.search(low_txt) if res is None else None
    if mk:
        sh, pe = val(mk[1]), val(mk[2].replace("-", " ") if mk[2] else "0")
        res = dict(rule="marked_shillings_pence", conf="high", low=[sh, pe], high=None, du="pence", dl=sh * 12 + pe, dh=None)
        hm = MARK_SD.search(high_txt) or MARK_S.search(high_txt)
        if hm:
            hs = val(hm[1]); hp = val(hm[2]) if hm.lastindex and hm.lastindex >= 2 and hm[2] else 0
            res["high"] = [hs, hp]; res["dh"] = hs * 12 + hp
    elif mp:
        pe = val(mp[1]) + int(mp[2]) / int(mp[3])
        res = dict(rule="marked_pence_fraction", conf="high", low=[pe], high=None, du="pence", dl=pe, dh=None)
    elif res is None and re.search(r"\d\s*d\b", low_txt) and not re.search(r"\d\s*s\b", low_txt):
        r["split_rule"], r["split_note"] = "unresolved", "pence_mark_without_shilling_mark"; cnt["unresolved:pence_mark_without_shilling_mark"] += 1; continue
    if res is None and len(T) == 3 and r["currency_unit"] == "lsd" and high_txt:
        H = [val(t) for t in TOK.findall(high_txt)]
        if len(H) == 3 and T[1] < 20 and T[2] < 12 and H[1] < 20 and H[2] < 12:
            pence = lambda x: x[0] * 240 + x[1] * 12 + x[2]
            if pence(H) >= pence(T):
                res = dict(rule="lsd_three_plus_three", conf="medium", low=T, high=H, du="pence", dl=pence(T), dh=pence(H))
    if res is None:
        res, why = split(T, r["currency_unit"])
    if res is None:
        r["split_rule"], r["split_note"] = "unresolved", why; cnt["unresolved:" + why] += 1; continue
    r["split_rule"], r["split_confidence"] = res["rule"], res["conf"]
    r["split_note"] = "inferred from number layout; check against image"
    r["price_low_parts"] = "-".join(fmt(x) for x in res["low"]); r["price_high_parts"] = "-".join(fmt(x) for x in res["high"]) if res["high"] else ""
    r["price_low_derived"] = fmt(res["dl"]); r["price_high_derived"] = "" if res["dh"] is None else fmt(res["dh"]); r["derived_unit"] = res["du"]
    cnt["split:" + res["rule"]] += 1
cols = list(rows[0].keys())
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
print(dict(cnt)); print("compound rows:", sum(cnt.values()))
