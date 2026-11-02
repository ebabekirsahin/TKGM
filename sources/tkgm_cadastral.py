"""TKGM public cadastral query using province/district/neighborhood and ada/parsel."""
import time
from urllib.parse import quote
import requests
from core.normalize import norm

BASE = "https://cbsapi.tkgm.gov.tr/megsiswebapi.v3.1/api"
IL_URL = "https://parselsorgu.tkgm.gov.tr/app/modules/administrativeQuery/data/ilListe.json"
IL_IDS = {"adana": 1, "afyonkarahisar": 3, "canakkale": 17, "malatya": 44, "manisa": 45}
SOURCE = "TKGM CBS / Parsel Sorgu"

def _admin_norm(value):
    key = norm(value)
    for suffix in ("mahallesi", "mahalle", "mah", "koyu", "koy"):
        if key.endswith(suffix) and len(key) > len(suffix):
            return key[:-len(suffix)]
    return key

def _records(data):
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        items = [x.get("properties") or {} for x in data.get("features", [])]
    elif isinstance(data, list):
        items = data
    else:
        items = []
    out = {}
    for p in items:
        d = {norm(k): v for k, v in p.items()}
        ident = d.get("id") or d.get("ilcekodu") or d.get("mahallekodu")
        name = d.get("text") or d.get("ad") or d.get("name") or d.get("ilceadi") or d.get("mahalleadi")
        if ident is not None and name:
            out[_admin_norm(name)] = {"id": str(ident), "name": str(name).strip()}
    return out

class TKGMClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"Accept":"application/json", "User-Agent":"Mozilla/5.0 (compatible; TasinmazHarita/1.0)", "Referer":"https://parselsorgu.tkgm.gov.tr/"})
        self.last = 0.0
        self.cache = {}
        self.provinces = None

    def get(self, url):
        wait = 0.35 - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        r = self.s.get(url, timeout=25)
        self.last = time.monotonic()
        if r.status_code in (401, 403, 429):
            raise RuntimeError(f"TKGM HTTP {r.status_code}; servis erişimi/kota nedeniyle işlem durduruldu.")
        r.raise_for_status()
        return r.json()

    def province(self, name):
        if self.provinces is None:
            try:
                self.provinces = _records(self.get(IL_URL))
            except Exception as exc:
                if "HTTP 403" in str(exc) or "HTTP 429" in str(exc):
                    raise
                self.provinces = {}
        key = _admin_norm(name)
        if key == "afyon":
            key = "afyonkarahisar"
        if key in self.provinces:
            return self.provinces[key]
        if key in IL_IDS:
            return {"id": str(IL_IDS[key]), "name": name}
        raise ValueError(f"İl TKGM listesinde bulunamadı: {name}")

    def admin_list(self, kind, parent_id):
        key = (kind, str(parent_id))
        if key not in self.cache:
            path = "ilceListe" if kind == "ilce" else "mahalleListe"
            data = self.get(f"{BASE}/idariYapi/{path}/{quote(str(parent_id), safe='')}")
            self.cache[key] = _records(data)
        return self.cache[key]

    def parcel(self, mahalle_id, ada, parsel):
        return self.get(f"{BASE}/parsel/{quote(str(mahalle_id), safe='')}/{quote(str(ada), safe='')}/{quote(str(parsel), safe='')}")

def _prop(props, keys):
    normalized = {norm(k): v for k, v in (props or {}).items()}
    for key in keys:
        value = normalized.get(norm(key))
        if value not in (None, ""):
            return value
    return None

def _to_feature(data, row, province, district, neighborhood):
    if not isinstance(data, dict) or data.get("Message") or data.get("error"):
        return None
    feature = data if data.get("type") == "Feature" else next(iter(data.get("features", [])), None)
    if not feature or not feature.get("geometry"):
        return None
    geometry = feature["geometry"]
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    props = dict(feature.get("properties") or {})
    ada = _prop(props, ("adaNo", "adano", "ada"))
    parsel = _prop(props, ("parselNo", "parselno", "parsel"))
    if ada is not None and norm(ada) != norm(row["ada_pafta"]):
        return None
    if parsel is not None and norm(parsel) != norm(row["parsel"]):
        return None
    props.update({"IL": row["il"], "ILCE": row["ilce"], "MAHALLE": row["mahalle"],
                  "ADA": str(ada if ada is not None else row["ada_pafta"]),
                  "PARSEL": str(parsel if parsel is not None else row["parsel"])})
    return {"type":"Feature", "geometry":geometry, "properties":props, "source":SOURCE}

def fetch_public_cadastral_parcels(rows, progress_callback=None):
    """Resolve unique cadastral keys; never guess a location when a lookup fails."""
    client = TKGMClient()
    output, errors, cache = [], [], {}
    unique = {}
    for row in rows:
        key = tuple(norm(row.get(k)) for k in ("il", "ilce", "mahalle")) + (str(row.get("ada_pafta", "")).strip(), str(row.get("parsel", "")).strip())
        unique.setdefault(key, row)
    total = len(unique)
    for i, (key, row) in enumerate(unique.items(), 1):
        try:
            if not all(key):
                raise ValueError("İl, ilçe, mahalle, ada ve parsel alanları dolu olmalı.")
            province = client.province(row["il"])
            district = client.admin_list("ilce", province["id"]).get(_admin_norm(row["ilce"]))
            if not district:
                raise ValueError(f"İlçe TKGM listesinde bulunamadı: {row['ilce']}")
            neighborhood = client.admin_list("mahalle", district["id"]).get(_admin_norm(row["mahalle"]))
            if not neighborhood:
                raise ValueError(f"Mahalle TKGM listesinde bulunamadı: {row['mahalle']}")
            parcel_key = (neighborhood["id"], str(row["ada_pafta"]).strip(), str(row["parsel"]).strip())
            if parcel_key not in cache:
                cache[parcel_key] = _to_feature(client.parcel(*parcel_key), row, province["name"], district["name"], neighborhood["name"])
            if cache[parcel_key]:
                output.append(cache[parcel_key])
        except Exception as exc:
            if "HTTP 403" in str(exc) or "HTTP 429" in str(exc):
                errors.append(str(exc))
                errors.append(f"Sorgu kısıt nedeniyle {i-1}/{total} kayıtta durduruldu.")
                break
            if len(errors) < 30:
                errors.append(f"Excel satırı {row.get('excel_satir', '?')}: {exc}")
        if progress_callback and (i % 10 == 0 or i == total):
            progress_callback(i, total, row)
    errors.insert(0, f"TKGM: {len(output):,} gerçek geometri / {total:,} benzersiz parsel anahtarı işlendi.")
    return output, errors
