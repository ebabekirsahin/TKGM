import requests

def fetch_public_wfs(url, type_name, limit=10000):
    if not url.lower().startswith("https://"):
        raise ValueError("Güvenlik için WFS adresi HTTPS olmalıdır.")
    params={"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":type_name,"outputFormat":"application/json","count":int(limit)}
    response=requests.get(url,params=params,timeout=(10,90),headers={"User-Agent":"TasinmazHarita/1.0"})
    response.raise_for_status()
    try: data=response.json()
    except Exception as exc: raise ValueError("WFS JSON/GeoJSON yanıtı döndürmedi.") from exc
    if data.get("type") not in ("FeatureCollection","Feature"):
        raise ValueError("WFS çıktısı GeoJSON FeatureCollection değil.")
    from sources.loaders import _feature_collection
    return _feature_collection(data, url)
