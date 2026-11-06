"""Check split_compound output against prices I (Claude) read from table IMAGES in the pilot. Not human-verified."""
import csv, sys
r = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
NY = "sn83021127_1783-07-03_1.pdf_/page/2/Table/11"
ny = [("Ashes, American",[1,10,0],[2,2,0]),("Do. Pot,",[2,0,0],[2,10,0]),("Bark, Jesuits",[0,3,0],[0,3,6]),("Do. 2d",[0,4,0],[0,4,3]),("Do. Quill",[0,5,3],[0,5,9]),
("Beef, Irish",[2,16,0],[2,18,0]),("Do. Cargo, B",[1,16,0],[2,4,0]),("Do. Irish Beef",[3,18,0],[4,0,0]),("Do. Cargo, Tierce",[3,10,0],[3,12,0]),("Butter, Irish, full",[2,18,0],None),
("Do. second",[2,16,0],None),("Indigo, Spanish",[0,14,0],[0,16,6]),("Do. French",[0,9,9],[0,10,3]),("Do. Carolina",[0,3,6],[0,7,6]),("Oil, Whale",[24,0,0],[25,0,0]),
("Do. Spermac",[45,0,0],[50,0,0]),("Rice, Carolina",[1,18,0],None),("Do. Italian",[1,9,0],[1,10,0]),("Rum, Jamaica",[0,3,0],[0,3,1]),("Do. Leeward",[0,2,6],[0,2,7]),
("Tea, Fine",[0,10,0],[0,12,0]),("Do. Common Hyson",[0,7,0],[0,7,6]),("Do. Souchong",[0,4,8],[0,6,6]),("Do. Bohea",[0,2,10.5],[0,2,11.5]),("Do. Congo",[0,4,0],[0,5,2]),
("Tobacco, Maryland",[0,1,11],[0,2,2]),("Do. Virginia, James",[0,1,11],[0,2,3]),("Do. Rappahannock",[0,1,9],[0,2,0]),("Wool, Beaver Wooms",[1,8,0],[1,14,0]),("Do. Beaver Coats",[1,0,0],[1,2,2])]
RIC = {"sn84024736_1810-03-06_1.pdf_/page/0/Table/5": [("TOBACCO",5.00),("FLOUR",6.50),("DO.",6.00),("CORN",3.33),("WHEAT",1.17),("BACON",0.10),("WHISKEY",0.67),("BAR IRON",110.0),("HEMP",250.0)],
       "sn84024736_1810-02-01_1.pdf_/page/0/Table/5": [("TOBACCO",5.00),("FLOUR",6.75),("DO.",6.25),("CORN",3.00),("WHEAT",1.17),("BACON",0.10),("WHISKEY",0.80),("BAR IRON",110.0),("HEMP",270.0)]}
def parts(s): return [float(x) for x in s.split("-")] if s else None
ok = bad = unres = nofind = 0; notes = []
for item, lo, hi in ny:
    m = [x for x in r if x["block_uid"] == NY and x["item_as_printed"].startswith(item)]
    if not m: nofind += 1; notes.append(("NO ROW", item)); continue
    x = m[0]
    if not x["price_low_parts"]: unres += 1; notes.append(("UNRESOLVED", item, x["split_note"])); continue
    if parts(x["price_low_parts"]) == [float(v) for v in lo] and (parts(x["price_high_parts"]) == ([float(v) for v in hi] if hi else None)): ok += 1
    else: bad += 1; notes.append(("MISMATCH", item, x["price_low_parts"], x["price_high_parts"], lo, hi))
print("NY 1783:", dict(ok=ok, mismatch=bad, unresolved=unres, row_not_found=nofind))
ok = bad = unres = nofind = 0
for uid, g in RIC.items():
    rows = [x for x in r if x["block_uid"] == uid]
    for item, v in g:
        m = [x for x in rows if x["item_as_printed"].upper().strip(" ,.:").startswith(item)]
        if not m: nofind += 1; notes.append(("NO ROW", uid[-26:], item)); continue
        x = m[0]
        d = x["price_low_derived"]
        if not d: unres += 1; notes.append(("UNRESOLVED/NOT COMPOUND", item, x["price_low_as_printed"], x["split_note"])); continue
        if abs(float(d) - v) < 1e-6: ok += 1
        else: bad += 1; notes.append(("MISMATCH", item, d, v))
print("Richmond 1810:", dict(ok=ok, mismatch=bad, unresolved_or_not_compound=unres, row_not_found=nofind))
for n in notes: print("  ", n)
