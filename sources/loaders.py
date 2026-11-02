import json
import zipfile
import io
import xml.etree.ElementTree as ET
import geopandas as gpd

def _feature_collection(data, source):
    if data.get("type") == "FeatureCollection": items = data.get("features",[])
    elif data.get("type") == "Feature": items = [data]
    else: raise ValueError("GeoJSON Feature veya FeatureCollection olmalı.")
    out=[]
    for f in items:
        if f.get("geometry"):
            out.append({"geometry":f["geometry"],"properties":f.get("properties") or {},"source":source})
    return out

def _kml(upload):
    root=ET.fromstring(upload.getvalue()); out=[]
    for pm in root.iter():
        if pm.tag.split("}")[-1] != "Placemark": continue
        props={}
        for el in pm.iter():
            tag=el.tag.split("}")[-1]
            if tag=="Data":
                val=next((x for x in el if x.tag.split("}")[-1]=="value"),None)
                if el.attrib.get("name") and val is not None: props[el.attrib["name"]]=val.text or ""
            if tag=="SimpleData" and el.attrib.get("name"): props[el.attrib["name"]]=el.text or ""
        # GeoPandas/Fiona KML reader, when available, handles holes and multipart geometry.
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".kml",delete=False) as tmp:
                tmp.write(upload.getvalue()); name=tmp.name
            gdf=gpd.read_file(name, driver="KML")
            os.unlink(name)
            for _,r in gdf.iterrows():
                if r.geometry is not None:
                    p={k:v for k,v in r.items() if k!="geometry"}
                    p.update(props)
                    out.append({"geometry":r.geometry.__geo_interface__,"properties":p,"source":upload.name})
            return out
        except Exception as exc:
            raise ValueError("KML sürücüsü bu ortamda desteklenmiyor; GeoJSON veya ZIP Shapefile kullanın.") from exc
    return out

def load_spatial_upload(upload):
    name=upload.name.lower()
    if name.endswith((".geojson",".json")):
        return _feature_collection(json.loads(upload.getvalue()), upload.name)
    if name.endswith(".kml"): return _kml(upload)
    if name.endswith(".zip"):
        try:
            gdf=gpd.read_file(io.BytesIO(upload.getvalue()))
            if gdf.crs is None: raise ValueError("Shapefile koordinat sistemi (.prj) tanımlı değil.")
            gdf=gdf.to_crs("EPSG:4326")
            return [{"geometry":r.geometry.__geo_interface__,"properties":{k:str(v) for k,v in r.items() if k!="geometry"},"source":upload.name} for _,r in gdf.iterrows() if r.geometry is not None]
        except Exception as exc: raise ValueError(f"ZIP Shapefile okunamadı: {exc}") from exc
    raise ValueError("Desteklenmeyen format.")
