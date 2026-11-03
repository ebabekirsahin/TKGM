from sources.curated_arcgis import _seyhan, _guid_sql


class FakeResponse:
    def __init__(self, features):
        self._data = {"features": features}

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params or {}))
        if url.endswith("/4/query"):
            return FakeResponse([{
                "attributes": {
                    "ADANO": "123",
                    "PARSELNO": "5",
                    "MAHALLEID": "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}",
                    "TIP": 2,
                },
                "geometry": {
                    "rings": [[[35.2, 37.0], [35.21, 37.0], [35.21, 37.01], [35.2, 37.01], [35.2, 37.0]]],
                    "spatialReference": {"wkid": 4326},
                },
            }])
        if url.endswith("/7/query"):
            return FakeResponse([{
                "attributes": {
                    "ID": "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}",
                    "AD": "Barbaros",
                    "ILCEID": "{bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb}",
                }
            }])
        if url.endswith("/6/query"):
            return FakeResponse([{
                "attributes": {
                    "ID": "{bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb}",
                    "AD": "Seyhan",
                }
            }])
        raise AssertionError(f"Unexpected query URL: {url}")


def test_guid_sql_uses_arcgis_braced_guid_literal():
    assert _guid_sql("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") == "'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'"


def test_seyhan_adapter_queries_cadastral_parcel_and_joins_admin_names():
    session = FakeSession()
    rows = [{
        "il": "Adana",
        "ilce": "Seyhan",
        "mahalle": "Barbaros",
        "ada_pafta": "123",
        "parsel": "5",
        "excel_satir": 2,
    }]
    output, notes = [], []

    _seyhan(session, rows, output, notes)

    assert len(output) == 1
    props = output[0]["properties"]
    assert props["IL"] == "Adana"
    assert props["ILCE"] == "Seyhan"
    assert props["MAHALLE"] == "Barbaros"
    assert props["ADA"] == "123"
    assert props["PARSEL"] == "5"
    assert output[0]["geometry"]["type"] == "Polygon"
    parcel_query = next(params for url, params in session.calls if url.endswith("/4/query"))
    assert "TIP=2" in parcel_query["where"]
