"""Public TKGM coordinate lookup.

This endpoint resolves a parcel only when a WGS84 coordinate is already known.
It does NOT resolve a parcel from province/district/neighborhood/block/parcel alone.
The endpoint is part of the public TKGM web client; it is not a documented bulk API.
Respect service availability and terms; do not bypass CAPTCHA, authentication or limits.
"""
import time
import requests

BASE = "https://cbsapi.tkgm.gov.tr/megsiswebapi.v3.1/api"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "TasinmazHarita/1.0",
    "Referer": "https://parselsorgu.tkgm.gov.tr/",
    "Origin": "https://parselsorgu.tkgm.gov.tr",
}
_last_request = 0.0

def lookup_parcel_by_coordinate(lat, lon, timeout=20):
    global _last_request
    if lat is None or lon is None or not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
        raise ValueError("Geçersiz WGS84 enlem/boylam.")
    # Conservative client-side pacing; do not retry rate limits or evade restrictions.
    wait = 0.5 - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    url = f"{BASE}/parsel/{float(lat):.8f}/{float(lon):.8f}/"
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    _last_request = time.monotonic()
    if response.status_code == 429:
        raise RuntimeError("TKGM servisi istek sınırı (429) döndürdü. İşlem durduruldu; daha hızlı tekrar denenmedi.")
    if response.status_code in (401,403):
        raise RuntimeError(f"TKGM koordinat servisi erişimi reddetti (HTTP {response.status_code}). Yetkisiz erişim denenmedi.")
    response.raise_for_status()
    data = response.json()
    # Public client response is normally a GeoJSON Feature; tolerate a FeatureCollection.
    if data.get("type") == "Feature":
        feature = data
    elif data.get("type") == "FeatureCollection" and data.get("features"):
        feature = data["features"][0]
    elif data.get("geometry"):
        feature = {"type":"Feature","geometry":data["geometry"],"properties":data.get("properties") or {}}
    else:
        raise ValueError("TKGM yanıtında parsel geometrisi bulunamadı.")
    if not feature.get("geometry"):
        raise ValueError("TKGM yanıtında gerçek parsel geometrisi yok.")
    return {"geometry":feature["geometry"],"properties":feature.get("properties") or {},"source":"TKGM herkese açık koordinat sorgusu"}
