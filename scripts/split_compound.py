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
    if n == 3 and cur == "lsd" and T[1] < 20 and T[2] < 12:
        pence = lambda x: x[0] * 240 + x[1] * 12 + x[2]
        return dict(rule="lsd_three_numbers_single", conf="medium", low=T, high=None, du="pence", dl=pence(T), dh=None), ""
    return None, f"n{n}_ambiguous"

rows = list(csv.DictReader(open(v2_path, encoding="utf-8")))
new = ["split_rule", "split_confidence", "split_note", "price_low_parts", "price_high_parts", "price_low_derived", "price_high_derived", "derived_unit"]
cnt = collections.Counter()
for r in rows:
    for c in new: r[c] = ""
    o = obs.get((r["block_uid"], r["row_no"], r["market_place"]), {})
    s = (o.get("suspect_fields") or {}).get("price_low", "")
    if not s.startswith("compound_number:"): continue
    T = [val(t.replace(" ", " ")) for t in TOK.findall(s.split(":", 1)[1])]
    res, why = split(T, r["currency_unit"])
    if res is None:
        r["split_rule"], r["split_note"] = "unresolved", why; cnt["unresolved:" + why] += 1; continue
    if res["rule"] == "lsd_three_numbers_single" and r["price_high_as_printed"]:
        H = [val(t) for t in TOK.findall(r["price_high_as_printed"])]
        if len(H) == 3 and H[1] < 20 and H[2] < 12:
            res["high"] = H; res["dh"] = H[0] * 240 + H[1] * 12 + H[2]; res["rule"] = "lsd_three_plus_three"
    r["split_rule"], r["split_confidence"] = res["rule"], res["conf"]
    r["split_note"] = "inferred from number layout; check against image"
    r["price_low_parts"] = "-".join(fmt(x) for x in res["low"]); r["price_high_parts"] = "-".join(fmt(x) for x in res["high"]) if res["high"] else ""
    r["price_low_derived"] = fmt(res["dl"]); r["price_high_derived"] = "" if res["dh"] is None else fmt(res["dh"]); r["derived_unit"] = res["du"]
    cnt["split:" + res["rule"]] += 1
cols = list(rows[0].keys())
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
print(dict(cnt)); print("compound rows:", sum(cnt.values()))
