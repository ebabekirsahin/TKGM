from core.geometry import geometry_summary

def test_polygon_center():
    geom={"type":"Polygon","coordinates":[[[29,41],[29.01,41],[29.01,41.01],[29,41.01],[29,41]]]}
    result=geometry_summary(geom)
    assert result is not None
    assert 40 < result[0] < 42
