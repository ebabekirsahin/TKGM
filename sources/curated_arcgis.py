"""Known public cadastral ArcGIS services with schema-specific adapters.

Only query rows inside each service's documented administrative footprint.
A source that lacks neighborhood identifiers produces review candidates, not
verified matches. No nationwide coverage is implied.
"""
import re
import requests
from pyproj import Transformer

KAST = "https://e-imar.kastamonuozelidare.gov.tr/arcgis/rest/services/IDARE_PUBLIC/TKGM_PUBLIC/FeatureServer"
PURSAKLAR = "https://cbs.pursaklar.bel.tr/webgis/rest/services/otomasyon/identify/MapServer/0"

def _n(value):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(c for c in s if c.isalnum())

def _sql(v):
    return "'" + str(v).replace("'", "''") + "'"

def _query(session, url, where, out_fields="*", out_sr=4326):
    response = session.get(url.rstrip("/") + "/query", params={
        "f":"json", "where":where, "outFields":out_fields,
        "returnGeometry":"true", "outSR":str(out_sr), "resultRecordCount":1000
    }, timeout=45)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data["error"].get("message","ArcGIS query error"))
    return data.get("features",[])

def _geo(geom, fallback_wkid):
    rings = (geom or {}).get("rings")
    if not rings:
        return None
    sr = (geom or {}).get("spatialReference",{})
    wkid = sr.get("latestWkid") or sr.get("wkid") or fallback_wkid
    if wkid != 4326:
        transformer = Transformer.from_crs(f"EPSG:{wkid}", "EPSG:4326", always_xy=True)
        rings = [[list(transformer.transform(x,y)) for x,y in ring] for ring in rings]
    return {"type":"Polygon","coordinates":rings}

def _kastamonu(session, rows, out, notes):
    local = [r for r in rows if _n(r.get("il")) == _n("Kastamonu")]
    if not local:
        notes.append("Kastamonu TKGM_PUBLIC: Excel'de Kastamonu kaydı yok; bu servis sorgulanmadı.")
        return
    base = KAST
    try:
        # The published parcel layer has no district/neighborhood names. Join
        # parcel.tapumahall -> Mahalleler.objectid -> İlceler.objectid.
        parcel_url = base + "/0"
        mahalle_url = base + "/1"
        district_url = base + "/2"
        pairs = {(str(r["ada_pafta"]).strip(),str(r["parsel"]).strip()) for r in local if r.get("ada_pafta") and r.get("parsel")}
        where = " OR ".join(f"(adano={_sql(a)} AND parselno={_sql(p)})" for a,p in list(pairs)[:400])
        if not where:
            notes.append("Kastamonu: Excel'de ada/parsel çifti boş.")
            return
        parcel_features = _query(session,parcel_url,where,out_sr=4326)
        mahalle_ids = {str((f.get("attributes") or {}).get("tapumahall")) for f in parcel_features
                       if (f.get("attributes") or {}).get("tapumahall") is not None}
        mahalle_by_id = {}
        for mid in mahalle_ids:
            rows_m = _query(session,mahalle_url,f"objectid={mid}",out_fields="objectid,tapumahall,kadastroma,ilceref",out_sr=4326)
            if rows_m:
                mahalle_by_id[mid] = rows_m[0].get("attributes") or {}
        district_ids = {str(v.get("ilceref")) for v in mahalle_by_id.values() if v.get("ilceref") is not None}
        district_by_id = {}
        for did in district_ids:
            rows_d = _query(session,district_url,f"objectid={did}",out_fields="objectid,ad",out_sr=4326)
            if rows_d:
                district_by_id[did] = (rows_d[0].get("attributes") or {}).get("ad","")
        for f in parcel_features:
            attrs = f.get("attributes") or {}
            mid = str(attrs.get("tapumahall",""))
            m = mahalle_by_id.get(mid,{})
            did = str(m.get("ilceref",""))
            props = dict(attrs)
            props.update({"IL":"Kastamonu","ILCE":district_by_id.get(did,""),
                          "MAHALLE":m.get("tapumahall") or m.get("kadastroma") or "",
                          "ADA":attrs.get("adano"),"PARSEL":attrs.get("parselno")})
            geometry = _geo(f.get("geometry"),4326)
            if geometry:
                out.append({"type":"Feature","geometry":geometry,"properties":props,
                            "source":"Kastamonu İl Özel İdaresi TKGM_PUBLIC"})
    except Exception as exc:
        notes.append(f"Kastamonu TKGM_PUBLIC sorgusu başarısız: {exc}")

def _pursaklar(session, rows, out, notes):
    local = [r for r in rows if _n(r.get("il")) == _n("Ankara") and _n(r.get("ilce")) == _n("Pursaklar")]
    if not local:
        notes.append("Pursaklar Belediyesi: Excel'de Ankara/Pursaklar kaydı yok; bu servis sorgulanmadı.")
        return
    try:
        # This public layer exposes only adaparsel, not neighborhood names.
        # Return geometry candidates, but matching marks them for manual review.
        clauses = []
        for r in local:
            a,p = str(r.get("ada_pafta","")).strip(),str(r.get("parsel","")).strip()
            for value in (f"{a}/{p}",f"{a}-{p}",f"{a} {p}",f"{a} / {p}"):
                clauses.append(f"adaparsel={_sql(value)}")
        if not clauses:
            return
        features = _query(session,PURSAKLAR," OR ".join(clauses[:300]),out_sr=4326)
        for f in features:
            attrs = f.get("attributes") or {}
            geometry = _geo(f.get("geometry"),3857)
            if not geometry:
                continue
            props = dict(attrs)
            props.update({"IL":"Ankara","ILCE":"Pursaklar","ADA-PAFTA":attrs.get("adaparsel","")})
            out.append({"type":"Feature","geometry":geometry,"properties":props,
                        "source":"Pursaklar Belediyesi açık PARSEL katmanı"})
    except Exception as exc:
        notes.append(f"Pursaklar açık parsel servisi başarısız: {exc}")

def fetch_curated_public_parcels(rows, max_features=15000):
    session = requests.Session()
    output, notes = [], []
    _kastamonu(session,rows,output,notes)
    _pursaklar(session,rows,output,notes)
    return output[:max_features], notes
