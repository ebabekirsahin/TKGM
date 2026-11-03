from core.normalize import norm
import json
from core.geometry import geometry_summary

ALIASES = {
 "il":["il","iladi","il_adi","province","city"],
 "ilce":["ilce","ilceadi","ilce_adi","ilcead","district","ilce_adi"],
 "mahalle":["mahalle","mahalleadi","mahalle_adi","mahallead","tapu_mah_adi","kadastroma","neighborhood","koy","köy"],
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

def _eq(a,b):
    return bool(a is not None and b is not None and norm(a)==norm(b))

def _parcel_pair(row, props):
    ada, parcel = get_prop(props,"ada"), get_prop(props,"parsel")
    if ada and parcel:
        return _eq(row["ada_pafta"],ada) and _eq(row["parsel"],parcel)
    combined = get_prop(props,"ada_pafta")
    if combined:
        import re
        pieces = re.split(r"[/\\-]",combined)
        if len(pieces)==2:
            return _eq(row["ada_pafta"],pieces[0].strip()) and _eq(row["parsel"],pieces[1].strip())
        return _eq(row["ada_pafta"],combined)
    return False

def _dedupe_identical_features(features):
    """Remove byte-for-byte identical parcel copies returned by two public sources.

    Distinct geometries sharing one cadastral key are intentionally retained so
    the caller sees an ambiguous candidate rather than a silently chosen shape.
    """
    seen = set()
    result = []
    for feature in features:
        geometry = feature.get("geometry")
        props = feature.get("properties") or {}
        parcel_key = tuple(norm(get_prop(props, field)) for field in ("il", "ilce", "mahalle", "ada", "parsel"))
        if not geometry or not all(parcel_key):
            result.append(feature)
            continue
        identity = parcel_key + (json.dumps(geometry, sort_keys=True, separators=(",", ":"), ensure_ascii=False),)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(feature)
    return result

def match_records(rows, features):
    features = _dedupe_identical_features(features)
    output, matched = [], []
    for row in rows:
        base = {
            "İL": row["il"],
            "İlçe": row["ilce"],
            "Mahalle": row["mahalle"],
            "ADA-PAFTA": row["ada_pafta"],
            "PARSEL": row["parsel"],
        }
        coordinate_points = row.get("coordinate_points") or []
        excel_lat = coordinate_points[0]["lat"] if coordinate_points else row.get("enlem")
        excel_lon = coordinate_points[0]["lon"] if coordinate_points else row.get("boylam")

        exact, review = [], []
        for feature in features:
            props = feature.get("properties") or {}
            src_il, src_ilce, src_mahalle = (get_prop(props, k) for k in ("il", "ilce", "mahalle"))
            if not _eq(row["il"], src_il) or not _parcel_pair(row, props):
                continue
            if src_ilce and not _eq(row["ilce"], src_ilce):
                continue
            if src_mahalle and not _eq(row["mahalle"], src_mahalle):
                continue
            if src_ilce and src_mahalle:
                exact.append(feature)
            else:
                review.append(feature)

        candidates = exact if exact else review
        if len(candidates) != 1:
            status = "Bulunamadı" if not candidates else "Doğrulanmalı"
            reason = (
                "Açık kaynakların kapsadığı alanlarda eşleşme bulunamadı."
                if not candidates
                else f"{len(candidates)} aday bulundu; tekil eşleşme doğrulanmalı."
            )
            if excel_lat is not None and excel_lon is not None:
                reason += " Excel koordinatı haritada ayrıca gösteriliyor; parsel sınırı olarak kabul edilmedi."
            output.append({
                **base, "Durum": status, "Enlem": excel_lat, "Boylam": excel_lon,
                "Parsel Alanı (m²)": None, "Veri Kaynağı": "",
                "Açıklama": reason, "Excel Satırı": row["excel_satir"],
            })
            continue

        feature = candidates[0]
        summary = geometry_summary(feature.get("geometry"))
        if not summary:
            output.append({
                **base, "Durum": "Doğrulanmalı", "Enlem": excel_lat, "Boylam": excel_lon,
                "Parsel Alanı (m²)": None, "Veri Kaynağı": feature.get("source", ""),
                "Açıklama": "Aday kayıtta geçerli polygon geometrisi yok.",
                "Excel Satırı": row["excel_satir"],
            })
            continue

        lat, lon, area = summary
        props = feature.get("properties") or {}
        confirmed = bool(get_prop(props, "ilce") and get_prop(props, "mahalle"))
        status = "Bulundu" if confirmed else "Doğrulanmalı"
        reason = (
            "İl, ilçe, mahalle, ada ve parsel eşleşti."
            if confirmed
            else "Ada/parsel ve il eşleşti; kaynak ilçe veya mahalle bilgisini yayımlamadığı için geometri aday olarak gösteriliyor."
        )
        output.append({
            **base, "Durum": status, "Enlem": lat, "Boylam": lon,
            "Parsel Alanı (m²)": area, "Veri Kaynağı": feature.get("source", ""),
            "Açıklama": reason, "Excel Satırı": row["excel_satir"],
        })
        matched.append({
            "type": "Feature",
            "geometry": feature["geometry"],
            "properties": {
                **base, "Enlem": lat, "Boylam": lon, "Durum": status,
                "Veri Kaynağı": feature.get("source", ""),
            },
        })
    import pandas as pd
    return pd.DataFrame(output), matched
