import folium
from folium.plugins import Fullscreen, MarkerCluster

def build_map(features):
    coords=[(f["properties"]["Enlem"],f["properties"]["Boylam"]) for f in features]
    center=[sum(x[0] for x in coords)/len(coords),sum(x[1] for x in coords)/len(coords)] if coords else [39,35]
    m=folium.Map(location=center,zoom_start=6,tiles="OpenStreetMap",control_scale=True)
    Fullscreen(position="topright").add_to(m)
    polygons=folium.FeatureGroup(name="Parsel sınırları",show=True)
    markers=MarkerCluster(name="Parsel merkezleri",show=True)
    for f in features:
        p=f["properties"]
        popup=folium.Popup("<br>".join([f"<b>{k}:</b> {p.get(k,'')}" for k in ("İL","İlçe","Mahalle","ADA-PAFTA","PARSEL","Enlem","Boylam","Veri Kaynağı")]),max_width=360)
        folium.GeoJson(f,style_function=lambda _:{"color":"#147d46","weight":2,"fillOpacity":0.15},tooltip=f"{p.get('İL')} / {p.get('İlçe')} / Ada {p.get('ADA-PAFTA')} Parsel {p.get('PARSEL')}",popup=popup).add_to(polygons)
        folium.Marker([p["Enlem"],p["Boylam"]],popup=popup,tooltip=f"{p.get('İL')} - {p.get('PARSEL')}").add_to(markers)
    polygons.add_to(m); markers.add_to(m); folium.LayerControl(collapsed=False).add_to(m)
    return m
