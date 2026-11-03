from sources.tkgm_cadastral import _records, _to_feature, fetch_public_cadastral_parcels, TKGMClient


def test_parse_tkgm_geojson_admin_lists():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": 17, "text": "Çanakkale"}},
            {"type": "Feature", "properties": {"id": 1, "text": "Merkez"}},
        ],
    }
    result = _records(payload)
    assert result["canakkale"]["id"] == "17"
    assert result["merkez"]["id"] == "1"


def test_only_real_polygon_and_matching_cadastral_keys_are_accepted():
    row = {"il": "Çanakkale", "ilce": "Merkez", "mahalle": "Barbaros Mahallesi", "ada_pafta": "123", "parsel": "7"}
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[26, 40], [26.1, 40], [26.1, 40.1], [26, 40.1], [26, 40]]]},
        "properties": {"adaNo": 123, "parselNo": 7},
    }
    accepted = _to_feature(feature, row, "Çanakkale", "Merkez", "Barbaros")
    assert accepted is not None
    assert accepted["properties"]["IL"] == "Çanakkale"
    assert accepted["geometry"]["type"] == "Polygon"

    mismatch = dict(feature)
    mismatch["properties"] = {"adaNo": 999, "parselNo": 7}
    assert _to_feature(mismatch, row, "Çanakkale", "Merkez", "Barbaros") is None


def test_lookup_uses_neighborhood_id_and_returns_geojson(monkeypatch):
    def province(self, name):
        return {"id": "17", "name": "Çanakkale"}

    def admin_list(self, kind, parent_id):
        if kind == "ilce":
            return {"merkez": {"id": "1701", "name": "Merkez"}}
        return {"barbaros": {"id": "170100", "name": "Barbaros"}}

    def parcel(self, neighborhood_id, ada, parsel):
        assert neighborhood_id == "170100"
        assert ada == "123"
        assert parsel == "7"
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[26, 40], [26.1, 40], [26.1, 40.1], [26, 40.1], [26, 40]]]},
            "properties": {"adaNo": 123, "parselNo": 7},
        }

    monkeypatch.setattr(TKGMClient, "province", province)
    monkeypatch.setattr(TKGMClient, "admin_list", admin_list)
    monkeypatch.setattr(TKGMClient, "parcel", parcel)

    rows = [{"il": "Çanakkale", "ilce": "Merkez", "mahalle": "Barbaros Mahallesi",
             "ada_pafta": "123", "parsel": "7", "excel_satir": 2}]
    features, notes = fetch_public_cadastral_parcels(rows)
    assert len(features) == 1
    assert features[0]["properties"]["MAHALLE"] == "Barbaros Mahallesi"
    assert any("1 gerçek geometri" in note for note in notes)
