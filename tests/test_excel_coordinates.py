import pandas as pd

from core.excel import normalize_excel, _parse_coordinate_values


def _base_row(**extra):
    data = {
        "İL": "Manisa",
        "İlçe": "Şehzadeler",
        "Mahalle": "1. Anafartalar",
        "ADA-PAFTA": "123",
        "PARSEL": "7",
    }
    data.update(extra)
    return pd.DataFrame([data])


def test_single_coordinate_pair_with_turkish_decimal_comma():
    df = _base_row(ENLEM="38,6191", BOYLAM="27,4289")
    rows, mapping, errors = normalize_excel(df)
    assert not errors
    assert rows[0]["coordinate_points"] == [{"lat": 38.6191, "lon": 27.4289}]


def test_multiple_coordinate_column_pairs_are_all_read():
    df = _base_row(
        ENLEM_1="38,6191",
        BOYLAM_1="27,4289",
        ENLEM_2="38.6200",
        BOYLAM_2="27.4300",
        LATITUDE_3="38.6210",
        LONGITUDE_3="27.4310",
    )
    rows, _, errors = normalize_excel(df)
    assert not errors
    points = rows[0]["coordinate_points"]
    assert len(points) == 3
    assert points[0] == {"lat": 38.6191, "lon": 27.4289}
    assert points[2] == {"lat": 38.621, "lon": 27.431}


def test_multiple_values_in_cells_use_semicolon_delimiter():
    df = _base_row(ENLEM="38.6;38.7", BOYLAM="27.4;27.5")
    rows, _, errors = normalize_excel(df)
    assert not errors
    assert rows[0]["coordinate_points"] == [
        {"lat": 38.6, "lon": 27.4},
        {"lat": 38.7, "lon": 27.5},
    ]


def test_invalid_out_of_range_coordinates_are_ignored():
    df = _base_row(ENLEM="91", BOYLAM="181")
    rows, _, errors = normalize_excel(df)
    assert not errors
    assert rows[0]["coordinate_points"] == []
    assert rows[0]["enlem"] is None
    assert rows[0]["boylam"] is None


def test_north_east_suffix_is_supported():
    assert _parse_coordinate_values("38.6N", "enlem") == [38.6]
    assert _parse_coordinate_values("27.4E", "boylam") == [27.4]
