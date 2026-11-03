from map_view.render import build_map


def test_turkey_map_renders_even_without_parcel_polygons():
    html = build_map([], coordinate_points=[]).get_root().render()
    assert "OpenStreetMap" in html
    assert "39.0" in html
    assert "Parsel sınırları" in html


def test_excel_coordinates_render_as_independent_markers():
    points = [
        {"lat": 38.6191, "lon": 27.4289, "il": "Manisa", "ilce": "Şehzadeler",
         "mahalle": "Anafartalar", "ada_pafta": "123", "parsel": "7", "excel_satir": 2},
        {"lat": 38.6200, "lon": 27.4300, "il": "Manisa", "ilce": "Şehzadeler",
         "mahalle": "Anafartalar", "ada_pafta": "124", "parsel": "8", "excel_satir": 3},
    ]
    html = build_map([], coordinate_points=points).get_root().render()
    assert "Excel koordinatları" in html
    assert "38.6191" in html
    assert "27.4289" in html
    assert "38.6200" in html
