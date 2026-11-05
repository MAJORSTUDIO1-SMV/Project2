#!/usr/bin/env python3
"""parse_tables_v2.py  -  conservative parser for price-current table blocks.

Rules: never invent/compute numbers beyond the printed D+C/100 or fraction;
keep printed text exact; null ONLY the suspect field; log every cell not turned
into an observation; no currency conversion.
Usage: python3 -I parse_tables_v2.py table_blocks_md.json outdir
"""
import json, re, sys, os, csv

AVAIL = re.compile(r"\b(none at market|none|no demand at any price|no demand|unfaleable|unsaleable|unsalable|scarce|plenty|nominal)\b", re.I)
UNIT = re.compile(r"\b(cwt|bbls?|bls?|bl|bb|barrels?|bushels?|bu|gallons?|gal|lbs?|tons?|tun|pipes?|hhds?|hogsheads?|doz(?:en)?|M|1200|quintals?|chal|bag|bags|ream|reams|keg|kegs|box|boxes)\b\.?", re.I)
CURR = re.compile(r"\b(dols?|dollars?|cts|cents?|\d+\s*s|\d+\s*d|s|d|l)\.?\b", re.I)
FIN = re.compile(r"per cent|\bdis\b\.?|discount|premium|bank|insurance|exchange on|bills on|stock|sterling", re.I)
NOTPRICE = re.compile(r"ARRIVED|CLEARED|\bSchr\.|\bBrig\b|\bShip\b|\bSloop\b", re.I)
DASH = "—–"
NUM = re.compile(r"\d+/\d+|\d+(?:\.\d+)?")


def split_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def is_sep(line):
    return re.fullmatch(r"\|?[\s\-:|]+\|?", line.strip()) is not None


def parse_block(md):
    """-> list of (heading_lines, rows) for each markdown table in the block."""
    lines = md.split("\n")
    out, head, rows = [], [], []
    for ln in lines:
        if ln.strip().startswith("|"):
            if is_sep(ln):
                continue
            rows.append(split_row(ln))
        else:
            if rows:
                out.append((head, rows)); head, rows = [], []
                head = []
            if ln.strip():
                head.append(re.sub(r"[*_<>/]|\bi\b", "", ln).strip() if False else ln.strip().strip("*").strip())
    if rows:
        out.append((head, rows))
    return out


def nums(s):
    """printed numbers in string with mixed fractions merged: '5 3/4' -> [5.75]; returns (values, raw tokens)."""
    toks = NUM.findall(s)
    vals, raw, i = [], [], 0
    while i < len(toks):
        t = toks[i]
        if "/" not in t and i + 1 < len(toks) and "/" in toks[i + 1]:
            a, (n, d) = float(t), toks[i + 1].split("/")
            vals.append(a + int(n) / int(d)); raw.append(t + " " + toks[i + 1]); i += 2; continue
        if "/" in t:
            n, d = t.split("/"); vals.append(int(n) / int(d))
        else:
            vals.append(float(t))
        raw.append(t); i += 1
    return vals, raw


def value_of(part):
    """single value from a text part, or (None, reason)."""
    v, raw = nums(part)
    if len(v) == 1:
        return v[0], None
    if len(v) == 0:
        return None, "no_number"
    return None, "compound_number:" + " ".join(raw)


def norm_market(heading):
    for h in heading[::-1]:
        t = re.sub(r"\(.*?\)", "", h).strip(" .*")
        if re.search(r"PRICES? CURRENT\.?$", t, re.I) and len(heading) > 1:
            continue
        return h
    return heading[-1] if heading else ""


def market_names(heading, npairs):
    for h in heading[::-1]:
        toks = re.split(r"(?<=\.)\s+", h.strip())
        merged, i = [], 0
        while i < len(toks):
            if re.fullmatch(r"[A-Z]\.", toks[i]) and i + 1 < len(toks):
                merged.append(toks[i] + " " + toks[i + 1]); i += 2
            else:
                merged.append(toks[i]); i += 1
        if len(merged) == npairs and not re.search(r"current", h, re.I):
            return [m.strip(" .") for m in merged], False
    return [f"market_{k+1}" for k in range(npairs)], True


def place_from_heading(heading):
    """Market named in heading, e.g. 'At Cadiz, May 29, 1800.' / 'Wholesale Prices Current at Boston.'"""
    for h in heading[::-1]:
        m = re.search(r"\b[Aa]t\s+([A-Z][\w\.\- ]+?)(?:,|\.|$)", h)
        if m:
            return m.group(1).strip()
        m = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)*),\s*[A-Z][a-z]+ \d+", h)
        if m:
            return m.group(1)
        m = re.search(r"Price Current of\s+([A-Z][\w ]+)", h, re.I)
        if m:
            return m.group(1).strip(" .")
    return None


def unit_in(text):
    m = UNIT.findall(text)
    return None if not m else m[-1]


class Ctx:
    def __init__(self):
        self.obs, self.fin, self.unparsed = [], [], []


def base(blk, tno, rno, heading, layout):
    return {
        "block_uid": blk["block_uid"], "table_no": tno, "row_no": rno,
        "filename": blk["filename"], "newspaper_id": blk["newspaper_id"],
        "issue_date": blk["date"], "page_number": blk["page_number"],
        "heading_as_printed": " / ".join(heading), "layout": layout,
    }


def mk_obs(b, item, market, **kw):
    o = dict(b)
    o.update({
        "item_as_printed": item, "market_place": market,
        "unit_as_printed": None, "unit_status": "not_stated",
        "price_low_as_printed": None, "price_high_as_printed": None,
        "price_low": None, "price_high": None, "price_scale": "unknown",
        "currency_as_printed": None, "availability_note": None,
        "ditto_of_previous": False, "flags": [], "suspect_fields": {},
        "confidence": "high",
    })
    o.update(kw)
    return o


def finalize(o):
    lo, hi = o["price_low"], o["price_high"]
    if lo is not None and hi is not None and o["price_scale"] in ("dollars", "cents"):
        if lo > hi:
            o["suspect_fields"]["price_high"] = "high<low"; o["price_high"] = None
        elif lo > 0 and hi / lo > 2.5:
            o["suspect_fields"]["price_high"] = "high>2.5x low (OCR?)"; o["price_high"] = None
    if o["price_scale"] == "unknown" and (lo is not None or hi is not None):
        o["flags"].append("price_scale_unknown")
    if o["suspect_fields"]:
        o["confidence"] = "low"
    elif o["flags"] and o["confidence"] == "high":
        o["confidence"] = "medium"
    return o


# ---------------------------------------------------------------- layouts
def layout_dc(ctx, blk, tno, heading, rows):
    hdr = rows[0]
    npairs = sum(1 for c in hdr[1:] if c.strip().upper() == "D.")
    markets, guessed = market_names(heading, npairs)
    prev_unit = None
    for rno, r in enumerate(rows[1:], start=1):
        r = r + [""] * (1 + 2 * npairs - len(r))
        label = r[0]
        b = base(blk, tno, rno, heading, "DC")
        made = 0
        free_avail = AVAIL.search(label)
        label_nums = nums(label)[0]
        unit = unit_in(label)
        ustat = "printed" if unit else "not_stated"
        if re.search(r"\bdo\.", label, re.I) and not unit:
            ustat = "ditto_of_previous"; unit = prev_unit
        if unit and ustat == "printed":
            prev_unit = unit
        avail_used = False
        for k in range(npairs):
            d, c = r[1 + 2 * k].strip(), r[2 + 2 * k].strip()
            mk = markets[k] + (" (market name uncertain)" if guessed else "")
            o = mk_obs(b, label, mk, unit_as_printed=unit, unit_status=ustat,
                       ditto_of_previous=(ustat == "ditto_of_previous"))
            if label_nums:
                o["flags"].append("label_contains_numbers")
            if guessed:
                o["flags"].append("market_name_guessed")
            if d and re.fullmatch(r"\d+", d) and c and re.fullmatch(r"\d+", c):
                o["price_low"] = int(d) + int(c) / 100; o["price_scale"] = "dollars"
                o["price_low_as_printed"] = f"{d} {c}"
            elif d and re.fullmatch(r"\d+", d) and not c:
                o["price_low"] = float(d); o["price_scale"] = "dollars"; o["price_low_as_printed"] = d
                t = re.search(r"\b(\d+)\s+to\s+(\d+)\s*[,.]?\s*$", label)
                if k == 0 and t and float(t.group(2)) == float(d):
                    o["price_low"], o["price_high"] = float(t.group(1)), float(t.group(2))
                    o["price_low_as_printed"] = t.group(0).strip(" ,.")
                    o["flags"].append("range_from_end_of_item_label_matches_cell")
            elif c and re.fullmatch(r"\d+", c) and not d:
                o["price_low"] = int(c) / 100; o["price_scale"] = "dollars"
                o["price_low_as_printed"] = c + " (cents column)"
                o["flags"].append("value_from_cents_column")
            elif (d or c):
                o["availability_note"] = (d or c); o["price_low_as_printed"] = None
                if not AVAIL.search(d or c):
                    o["flags"].append("unrecognised_text_in_price_cell"); o["confidence"] = "low"
            elif k == 0 and re.search(r"\b\d+(?:\s+to\s+\d+)?\s*[,.]?\s*$", label) and not free_avail:
                t = re.search(r"\b(\d+)(?:\s+to\s+(\d+))?\s*[,.]?\s*$", label)
                o["price_low"] = float(t.group(1)); o["price_scale"] = "dollars"
                o["price_low_as_printed"] = t.group(0).strip(" ,.")
                if t.group(2):
                    o["price_high"] = float(t.group(2))
                o["flags"].append("price_taken_from_end_of_item_label_first_market")
            else:
                if free_avail and not avail_used:
                    o["availability_note"] = free_avail.group(1) + " (from item label)"
                    o["flags"].append("availability_from_label"); avail_used = True
                else:
                    continue
            tail = re.search(r"\b(\d+)(?:\s+to\s+(\d+))?\s*[,.]?\s*$", label)
            if k == 0 and tail and o["price_low"] is None and not o["availability_note"]:
                pass
            ctx.obs.append(finalize(o)); made += 1
        if made == 0:
            ctx.unparsed.append({**b, "cells": r, "reason": "row_with_no_price_cells"})


def two_part(s):
    return [p.strip() for p in re.split(r"[—–]", s)]


def layout_boston(ctx, blk, tno, heading, rows):
    market = place_from_heading(heading)
    prev = None
    for rno, r in enumerate(rows[1:], start=1):
        r = r + [""] * (3 - len(r))
        label, a, bcell = r[0], r[1].strip(), r[2].strip()
        if a.lower().startswith("dols") or bcell.lower().startswith("cts"):
            continue
        if not (a or bcell):
            continue
        b = base(blk, tno, rno, heading, "FromTo_DolsCts")
        o = mk_obs(b, label, market, unit_as_printed=unit_in(label),
                   unit_status="printed" if unit_in(label) else "not_stated")
        if re.search(r"\bdo\.", label, re.I) and not unit_in(label):
            o["unit_status"] = "ditto_of_previous"; o["ditto_of_previous"] = True
        o["price_low_as_printed"] = (a + " | " + bcell).strip(" |")
        parts = two_part(bcell) if bcell else []
        if re.fullmatch(r"\d+", a):
            frm = int(a)
            left = parts[0] if parts else ""
            lv, _ = (value_of(left) if left else (None, None))
            o["price_low"] = frm + (int(lv) / 100 if lv is not None else 0)
            if lv is not None:
                o["price_scale"] = "dollars"
                if len(left.strip()) == 1:
                    o["flags"].append("single_digit_cents_may_be_zero_padded"); o["suspect_fields"]["price_low"] = "single-digit cents (e.g. '3' could be 03)"
            else:
                o["price_scale"] = "unknown"
                o["flags"].append("bare_number_dollars_or_cents_depends_on_unit")
            if len(parts) > 1:
                right = parts[1]
                o["price_high_as_printed"] = right
                v, raw = nums(right)
                if len(v) == 2:
                    o["price_high"] = v[0] + v[1] / 100
                    if len(right.split()[-1]) == 1:
                        o["flags"].append("single_digit_cents_in_high"); o["suspect_fields"]["price_high"] = "single-digit cents"
                    if o["price_scale"] == "unknown":
                        o["flags"].append("mixed_scale_possible")
                elif len(v) == 1:
                    o["price_high"] = v[0]; o["flags"].append("high_single_number_scale_follows_low")
                elif len(v) == 0:
                    o["flags"].append("high_missing_after_dash")
                else:
                    o["suspect_fields"]["price_high"] = "compound:" + " ".join(raw)
            elif bcell and not parts[0]:
                pass
        elif a in ("", "—", "-", "–"):
            o["flags"].append("from_dollars_blank_cents_only_unverified")
            if len(parts) == 2:
                lo, _ = value_of(parts[0]); hi, _ = value_of(parts[1])
                o["price_low"], o["price_high"] = lo, hi
                o["price_low_as_printed"], o["price_high_as_printed"] = parts[0], parts[1]
            elif len(parts) == 1:
                lo, _ = value_of(parts[0]); o["price_low"] = lo
                o["price_low_as_printed"] = parts[0]
            o["price_scale"] = "unknown"
        else:
            o["suspect_fields"]["price_low"] = f"From cell not numeric: '{a}'"
            ctx.unparsed.append({**b, "cells": r, "reason": "from_cell_not_numeric"})
        ctx.obs.append(finalize(o))


def layout_portland(ctx, blk, tno, heading, rows):
    market = place_from_heading(heading)
    for rno, r in enumerate(rows[1:], start=1):
        r = r + [""] * (4 - len(r))
        label = r[0]
        body = " ".join(c for c in r[1:] if c)
        if not body or body.lower().startswith("dols"):
            continue
        b = base(blk, tno, rno, heading, "FromTo_inline_units")
        unit = unit_in(body) or unit_in(label)
        o = mk_obs(b, label, market, unit_as_printed=unit,
                   unit_status="printed" if unit_in(body) else ("printed" if unit_in(label) else "not_stated"))
        o["price_low_as_printed"] = body
        groups = [g.strip() for g in re.split(r"[—–]", body) if g.strip()]
        gv = []
        for g in groups:
            g2 = UNIT.sub("", g)
            v, raw = nums(g2)
            gv.append(v)
        flat = [x for v in gv for x in v]
        if not flat:
            ctx.unparsed.append({**b, "cells": r, "reason": "no_numbers"}); continue
        def grp(v):
            if len(v) == 1: return v[0], "single"
            if len(v) == 2 and v[1] < 100 and float(v[0]).is_integer() and float(v[1]).is_integer():
                return v[0] + v[1] / 100, "dc"
            return None, "ambiguous"
        vals = [grp(v) for v in gv if v]
        o["price_scale"] = "dollars" if any(k == "dc" for _, k in vals) else "unknown"
        if len(vals) >= 1: o["price_low"] = vals[0][0]
        if len(vals) == 2: o["price_high"] = vals[1][0]
        if len(vals) > 2:
            o["flags"].append("more_than_two_groups"); o["confidence"] = "low"
        if any(k == "ambiguous" for _, k in vals):
            o["flags"].append("ambiguous_number_group")
            for i, (v, k) in enumerate(vals[:2]):
                if k == "ambiguous":
                    o["suspect_fields"]["price_low" if i == 0 else "price_high"] = "ambiguous digits: " + " ".join(map(str, gv[i]))
        o["flags"].append("portland_layout_dollar_vs_cents_unverified")
        o["confidence"] = "low" if o["suspect_fields"] else "medium"
        ctx.obs.append(finalize(o))


def generic_row(ctx, blk, tno, rno, heading, market, label, body, layout, cells):
    b = base(blk, tno, rno, heading, layout)
    unit = unit_in(body) or unit_in(label)
    o = mk_obs(b, label, market, unit_as_printed=unit,
               unit_status="printed" if unit else "not_stated")
    av = AVAIL.search(label + " " + body)
    if av:
        o["availability_note"] = av.group(1)
    cu = re.findall(r"\b\d+\s*[sd]\b\.?|\bdols?\b\.?|\bdollars?\b", body, re.I)
    if cu:
        o["currency_as_printed"] = " ".join(cu)
    o["price_low_as_printed"] = body
    body2 = UNIT.sub(" ", body)
    parts = [p for p in re.split(r"\s+(?:a|to)\s+|[—–]", body2) if NUM.search(p)]
    if not parts:
        if av:
            ctx.obs.append(finalize(o)); return
        ctx.unparsed.append({**b, "cells": cells, "reason": "no_numbers_in_row"}); return
    if len(parts) > 2:
        o["flags"].append("more_than_two_parts"); o["suspect_fields"]["price_low"] = "unclear parts"
        ctx.obs.append(finalize(o)); return
    for i, p in enumerate(parts):
        v, why = value_of(re.sub(r"\b\d+\s*[sd]\b\.?", lambda m: re.sub(r"\D", "", m.group(0)), p))
        key = "price_low" if i == 0 else "price_high"
        if v is None:
            o["suspect_fields"][key] = why
        else:
            o[key] = v
    if len(parts) == 2:
        o["price_low_as_printed"], o["price_high_as_printed"] = parts[0].strip(), parts[1].strip()
    # scale: dollars only when "dols"/Dollars heading says so
    if (o["currency_as_printed"] and re.search(r"dol", o["currency_as_printed"], re.I)) or \
       re.search(r"dollars", " ".join(heading) + " ".join(cells[:1]), re.I):
        o["price_scale"] = "dollars"
    ctx.obs.append(finalize(o))


def layout_generic(ctx, blk, tno, heading, rows, layout="generic"):
    market = place_from_heading(heading)
    hdr_text = " ".join(rows[0]) if rows else ""
    has_hdr = bool(re.search(r"dollars|dols|^$", rows[0][1] if len(rows[0]) > 1 else "", re.I)) and not NUM.search(hdr_text)
    start = 1 if has_hdr and re.search(r"[A-Za-z]", hdr_text) is not None and not NUM.search(hdr_text) and rows[0][0] == "" else 0
    if rows and rows[0][0] == "" and not NUM.search(hdr_text):
        start = 1
    hdr_cur = " ".join(rows[0]) if start else ""
    for rno, r in enumerate(rows[start:], start=start):
        label = r[0]
        body = " ".join(c for c in r[1:] if c)
        if len(r) == 1 or (not body):
            # prose row (one column) or label-only row
            m = re.match(r"^(.*?[A-Za-z\.\)])\s+((?:\d[\d/ ]*)(?:\s*(?:a|to)\s*\d[\d/ ]*)?.*)$", label)
            if m and NUM.search(m.group(2)) and len(r) == 1:
                generic_row(ctx, blk, tno, rno, heading + ([hdr_cur] if hdr_cur else []), market, m.group(1), m.group(2), layout + "_prose", r)
                continue
            b = base(blk, tno, rno, heading, layout)
            if label.strip():
                if AVAIL.search(label):
                    o = mk_obs(b, label, market, availability_note=AVAIL.search(label).group(1))
                    o["flags"].append("availability_only_line"); ctx.obs.append(finalize(o))
                else:
                    ctx.unparsed.append({**b, "cells": r, "reason": "note_or_label_without_price"})
            continue
        generic_row(ctx, blk, tno, rno, heading + ([hdr_cur] if hdr_cur else []), market, label, body, layout, r)


def layout_financial(ctx, blk, tno, heading, rows):
    section = None
    for rno, r in enumerate(rows):
        r = r + [""] * (2 - len(r))
        inst, quote = r[0].strip(), " ".join(c for c in r[1:] if c).strip()
        b = base(blk, tno, rno, heading, "financial")
        if inst and not quote:
            section = inst; continue
        if not inst and not quote:
            continue
        low = quote.lower()
        hint = ("percent_discount" if re.search(r"dis", low) else
                "percent_premium" if re.search(r"prem", low) else "unclear")
        ctx.fin.append({**b, "section_as_printed": section,
                        "instrument_as_printed": re.sub(r"(\s?\.){2,}", "", inst).strip(" ."),
                        "quote_as_printed": quote,
                        "quote_basis_hint_from_printed_words": hint,
                        "numbers_in_quote_as_printed": nums(quote)[1],
                        "flags": [], "confidence": "medium"})


def classify(heading, rows):
    text = " ".join(" ".join(r) for r in rows)
    htext = " ".join(heading)
    if not NUM.search(text):
        return "no_digits"
    nrows = max(1, len(rows))
    if len(NOTPRICE.findall(text)) >= 3 and not re.search(r"price", htext, re.I):
        return "not_prices"
    fin_rows = sum(1 for r in rows if re.search(r"per cent|\bdis\b\.?|discount|premium|per ct", " ".join(r), re.I))
    if fin_rows >= 3 or re.search(r"bank notes|bank note|exchange", htext, re.I) and fin_rows >= 1:
        return "financial"
    hdr = [c.strip().upper() for c in rows[0]]
    if hdr.count("D.") >= 1 and hdr.count("C.") >= 1:
        return "DC"
    sub = " ".join(" ".join(r) for r in rows[:2])
    if re.search(r"\bFrom\b", sub) and re.search(r"\bTo\b", sub):
        if any(re.search(r"Dols\.?\s*Cts\.?", c) for r in rows[:2] for c in r):
            return "portland"
        return "boston"
    return "generic"


def main(inp, outdir):
    os.makedirs(outdir, exist_ok=True)
    blocks = json.load(open(inp))
    ctx = Ctx()
    summary = []
    for blk in blocks:
        tables = parse_block(blk["block_markdown"])
        if not tables:
            ctx.unparsed.append({"block_uid": blk["block_uid"], "reason": "no_markdown_table_found",
                                 "text": blk["block_markdown"][:300]})
            summary.append((blk["block_uid"], "none", 0)); continue
        for tno, (heading, rows) in enumerate(tables):
            n0 = len(ctx.obs) + len(ctx.fin)
            kind = classify(heading, rows)
            if kind == "no_digits" or kind == "not_prices":
                ctx.unparsed.append({"block_uid": blk["block_uid"], "table_no": tno, "filename": blk["filename"],
                                     "issue_date": blk["date"], "reason": "table_" + kind,
                                     "heading_as_printed": " / ".join(heading),
                                     "text": json.dumps(rows, ensure_ascii=False)[:500]})
            elif kind == "financial":
                layout_financial(ctx, blk, tno, heading, rows)
            elif kind == "DC":
                layout_dc(ctx, blk, tno, heading, rows)
            elif kind == "boston":
                layout_boston(ctx, blk, tno, heading, rows)
            elif kind == "portland":
                layout_portland(ctx, blk, tno, heading, rows)
            else:
                layout_generic(ctx, blk, tno, heading, rows)
            summary.append((blk["block_uid"], kind, len(ctx.obs) + len(ctx.fin) - n0))
    json.dump(ctx.obs, open(f"{outdir}/observations_v2.json", "w"), indent=1, ensure_ascii=False)
    json.dump(ctx.fin, open(f"{outdir}/financial_quotes_v2.json", "w"), indent=1, ensure_ascii=False)
    json.dump(ctx.unparsed, open(f"{outdir}/unparsed_cells_v2.json", "w"), indent=1, ensure_ascii=False)
    with open(f"{outdir}/review_queue_v2.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block_uid", "row_no", "market", "item_as_printed", "price_low_as_printed",
                    "price_low", "price_high", "scale", "confidence", "flags", "suspect_fields"])
        for o in ctx.obs:
            if o["confidence"] != "high":
                w.writerow([o["block_uid"], o["row_no"], o["market_place"], o["item_as_printed"],
                            o["price_low_as_printed"], o["price_low"], o["price_high"], o["price_scale"],
                            o["confidence"], ";".join(o["flags"]), json.dumps(o["suspect_fields"])])
    json.dump(summary, open(f"{outdir}/table_summary_v2.json", "w"), indent=1)
    from collections import Counter
    print("tables by kind:", Counter(k for _, k, _ in summary))
    print("goods obs:", len(ctx.obs), "| financial rows:", len(ctx.fin), "| unparsed entries:", len(ctx.unparsed))
    print("confidence:", Counter(o["confidence"] for o in ctx.obs))
    print("scale:", Counter(o["price_scale"] for o in ctx.obs))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
