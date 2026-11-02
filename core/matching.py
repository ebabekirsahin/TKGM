from collections import defaultdict
from core.normalize import norm
from core.geometry import geometry_summary

ALIASES = {
 "il":["il","iladi","il_adi","province","city"],
 "ilce":["ilce","ilceadi","ilce_adi","ilcead","district"],
 "mahalle":["mahalle","mahalleadi","mahalle_adi","mahallead","koy","köy","neighborhood"],
 "ada":["ada","adano","ada_no","block"],
 "ada_pafta":["adapafta","ada_pafta","ada-pafta","ada pafta"],
 "parsel":["parsel","parselno","parsel_no","parcel"]
}

def get_prop(props, field):
    lookup = {norm(k): v for k,v in (props or {}).items()}
    for alias in ALIASES[field]:
        if norm(alias) in lookup:
            v = lookup[norm(alias)]
            return "" if v is None else str(v).strip()
    return ""

def feature_key(props):
    return tuple(norm(get_prop(props,k)) for k in ("il","ilce","mahalle","parsel"))

def match_records(rows, features):
    index = defaultdict(list)
    for f in features:
        p = f.get("properties") or {}
        key = feature_key(p)
        if all(key): index[key].append(f)
    output, matched = [], []
    for row in rows:
        base = { "İL":row["il"], "İlçe":row["ilce"], "Mahalle":row["mahalle"], "ADA-PAFTA":row["ada_pafta"], "PARSEL":row["parsel"] }
        key = tuple(norm(row[k]) for k in ("il","ilce","mahalle","parsel"))
        candidates = index.get(key, [])
        # Ada/pafta must also match exactly against one recognized source property.
        candidates = [f for f in candidates if norm(row["ada_pafta"]) in {
            norm(get_prop(f.get("properties",{}),"ada")),
            norm(get_prop(f.get("properties",{}),"ada_pafta"))
        }]
        if len(candidates) != 1:
            status = "Bulunamadı" if not candidates else "Doğrulanmalı"
            reason = "Açık veri kaynağında eşleşme yok." if not candidates else f"{len(candidates)} aday bulundu; tekil eşleşme doğrulanmalı."
            output.append({**base,"Durum":status,"Enlem":None,"Boylam":None,"Parsel Alanı (m²)":None,"Veri Kaynağı":"","Açıklama":reason,"Excel Satırı":row["excel_satir"]})
            continue
        f = candidates[0]
        summary = geometry_summary(f.get("geometry"))
        if not summary:
            output.append({**base,"Durum":"Doğrulanmalı","Enlem":None,"Boylam":None,"Parsel Alanı (m²)":None,"Veri Kaynağı":f.get("source",""),"Açıklama":"Eşleşen kayıtta geçerli polygon geometrisi yok.","Excel Satırı":row["excel_satir"]})
            continue
        lat, lon, area = summary
        output.append({**base,"Durum":"Bulundu","Enlem":lat,"Boylam":lon,"Parsel Alanı (m²)":area,"Veri Kaynağı":f.get("source",""),"Açıklama":"Beş alan ve polygon geometrisi eşleşti.","Excel Satırı":row["excel_satir"]})
        matched.append({"type":"Feature","geometry":f["geometry"],"properties":{**base,"Enlem":lat,"Boylam":lon,"Durum":"Bulundu","Veri Kaynağı":f.get("source","")}})
    import pandas as pd
    return pd.DataFrame(output), matched
