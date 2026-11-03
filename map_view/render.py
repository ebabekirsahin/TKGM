import folium
from folium.plugins import Fullscreen, MarkerCluster

TURKEY_CENTER = [39.0, 35.0]

def build_map(features, coordinate_points=None):
    """Render parcel polygons plus every valid coordinate supplied in Excel.

    Coordinate markers are an independent layer: the Turkey basemap remains
    visible even when no cadastral polygon has matched.
    """
    coordinate_points = coordinate_points or []
    polygon_centers = []
    for feature in features:
        props = feature.get("properties") or {}
        if props.get("Enlem") is not None and props.get("Boylam") is not None:
            polygon_centers.append((float(props["Enlem"]), float(props["Boylam"])))

    all_coords = [(float(p["lat"]), float(p["lon"])) for p in coordinate_points]
    if all_coords:
        center = [sum(p[0] for p in all_coords) / len(all_coords),
                  sum(p[1] for p in all_coords) / len(all_coords)]
        zoom = 6 if len(all_coords) > 1 else 13
    elif polygon_centers:
        center = [sum(p[0] for p in polygon_centers) / len(polygon_centers),
                  sum(p[1] for p in polygon_centers) / len(polygon_centers)]
        zoom = 10
    else:
        center, zoom = TURKEY_CENTER, 6

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap",
                   control_scale=True, prefer_canvas=True)
    Fullscreen(position="topright").add_to(m)

    polygons = folium.FeatureGroup(name="Parsel sınırları", show=True)
    polygon_markers = MarkerCluster(name="Parsel merkezleri", show=True)
    for feature in features:
        props = feature.get("properties") or {}
        info = [
            ("İl", props.get("İL", "")),
            ("İlçe", props.get("İlçe", "")),
            ("Mahalle", props.get("Mahalle", "")),
            ("Ada", props.get("ADA-PAFTA", "")),
            ("Parsel", props.get("PARSEL", "")),
            ("Enlem", props.get("Enlem", "")),
            ("Boylam", props.get("Boylam", "")),
            ("Kaynak", props.get("Veri Kaynağı", "")),
        ]
        popup = folium.Popup("<br>".join(f"<b>{k}:</b> {v}" for k, v in info), max_width=360)
        tooltip = f"{props.get('İL', '')} / {props.get('İlçe', '')} / Ada {props.get('ADA-PAFTA', '')} Parsel {props.get('PARSEL', '')}"
        folium.GeoJson(feature, style_function=lambda _: {"color":"#147d46","weight":2,"fillOpacity":0.15},
                       tooltip=tooltip, popup=popup).add_to(polygons)
        if props.get("Enlem") is not None and props.get("Boylam") is not None:
            folium.Marker([float(props["Enlem"]), float(props["Boylam"])],
                          popup=popup, tooltip=tooltip).add_to(polygon_markers)

    coordinate_layer = folium.FeatureGroup(name="Excel koordinatları", show=True)
    coord_cluster = MarkerCluster(name="Excel koordinat noktaları")
    for point in coordinate_points:
        lat, lon = float(point["lat"]), float(point["lon"])
        label = (f"{point.get('il', '')} / {point.get('ilce', '')} / "
                 f"{point.get('mahalle', '')} — Excel satırı {point.get('excel_satir', '')}")
        popup = folium.Popup(
            f"<b>Excel satırı:</b> {point.get('excel_satir', '')}<br>"
            f"<b>İl:</b> {point.get('il', '')}<br>"
            f"<b>İlçe:</b> {point.get('ilce', '')}<br>"
            f"<b>Mahalle:</b> {point.get('mahalle', '')}<br>"
            f"<b>Ada:</b> {point.get('ada_pafta', '')}<br>"
            f"<b>Parsel:</b> {point.get('parsel', '')}<br>"
            f"<b>Enlem:</b> {lat:.8f}<br><b>Boylam:</b> {lon:.8f}",
            max_width=360
        )
        folium.Marker([lat, lon], popup=popup, tooltip=label,
                      icon=folium.Icon(color="blue", icon="map-marker")).add_to(coord_cluster)

    polygons.add_to(m)
    polygon_markers.add_to(m)
    coord_cluster.add_to(coordinate_layer)
    coordinate_layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    if len(all_coords) > 1:
        m.fit_bounds(all_coords, padding=(25, 25))
    return m
