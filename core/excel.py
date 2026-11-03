import re
import pandas as pd
from core.normalize import norm, clean

ALIASES = {
 "il": ["il","ili"], "ilce": ["ilce","ilçesi","ilcesi"],
 "mahalle": ["mahalle","mahalle adı","mahalle adi","köy","koy"],
 "ada_pafta": ["ada-pafta","ada pafta","adapafta","ada","ada_no","adano"],
 "parsel": ["parsel","parsel no","parsel_no"]
}
LABELS = {"il":"İL","ilce":"İlçe","mahalle":"Mahalle","ada_pafta":"ADA-PAFTA","parsel":"PARSEL"}

def read_excel(uploaded):
    return pd.read_excel(uploaded, dtype=object)

def _coordinate_axis(column):
    """Return (axis, pair-key) for headers such as ENLEM, ENLEM_2, LATITUDE2."""
    header = norm(column)
    aliases = (
        ("enlem", ("enlem", "latitude", "lat")),
        ("boylam", ("boylam", "longitude", "long", "lng", "lon")),
    )
    for axis, prefixes in aliases:
        for prefix in prefixes:
            if header.startswith(prefix):
                suffix = header[len(prefix):]
                return axis, suffix or "default"
    # X/Y are accepted only when explicitly named as coordinate columns.
    if header in ("xcoord", "xcoordinate", "xkoordinat"):
        return "boylam", "default"
    if header in ("ycoord", "ycoordinate", "ykoordinat"):
        return "enlem", "default"
    return None

def _parse_coordinate_values(value, axis):
    """Parse decimal numbers, Turkish decimal commas and N/S/E/W suffixes."""
    if value is None or pd.isna(value):
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        values = [float(value)]
    else:
        raw = str(value).strip()
        if not raw:
            return []
        # Multiple values in one cell must use an explicit delimiter. A comma
        # remains a decimal separator, avoiding ambiguity in Turkish Excel.
        tokens = re.split(r"[;|\n]+", raw)
        values = []
        for token in tokens:
            token = token.strip().upper().replace("−", "-")
            if not token:
                continue
            direction_match = re.search(r"([NSEW])$", token)
            direction = direction_match.group(1) if direction_match else ""
            if direction:
                token = token[:-1]
            token = token.replace("°", "").replace("º", "").replace(" ", "")
            if token.count(",") == 1 and "." not in token:
                token = token.replace(",", ".")
            elif "," in token and "." in token:
                # In coordinates, the last separator is the decimal mark.
                if token.rfind(",") > token.rfind("."):
                    token = token.replace(".", "").replace(",", ".")
                else:
                    token = token.replace(",", "")
            try:
                number = float(token)
            except (TypeError, ValueError):
                continue
            if direction in ("S", "W"):
                number = -abs(number)
            elif direction in ("N", "E"):
                number = abs(number)
            values.append(number)
    limit = 90 if axis == "enlem" else 180
    return [v for v in values if -limit <= v <= limit]

def _coordinate_pairs(df, row):
    groups = {}
    for column in df.columns:
        parsed = _coordinate_axis(column)
        if not parsed:
            continue
        axis, pair_key = parsed
        groups.setdefault(pair_key, {})[axis] = column
    # Stable order: generic ENLEM/BOYLAM first, then numbered pairs.
    def order(item):
        key = item[0]
        if key == "default":
            return (0, 0, "")
        if key.isdigit():
            return (1, 0, int(key))
        return (1, 1, key)
        return (0 if key == "default" else 1, int(key) if key.isdigit() else key)
    pairs = []
    for _, columns in sorted(groups.items(), key=order):
        if "enlem" not in columns or "boylam" not in columns:
            continue
        latitudes = _parse_coordinate_values(row[columns["enlem"]], "enlem")
        longitudes = _parse_coordinate_values(row[columns["boylam"]], "boylam")
        for lat, lon in zip(latitudes, longitudes):
            pairs.append({"lat": lat, "lon": lon})
    return pairs

def normalize_excel(df):
    lookup = {norm(c): c for c in df.columns}
    mapping = {}
    missing = []
    for key, aliases in ALIASES.items():
        col = next((lookup[norm(a)] for a in aliases if norm(a) in lookup), None)
        if col is None:
            missing.append(LABELS[key])
        else:
            mapping[key] = col
    if missing:
        return [], mapping, missing

    rows = []
    for idx, row in df.iterrows():
        item = {key: clean(row[col]) for key, col in mapping.items()}
        item["excel_satir"] = int(idx) + 2
        coordinates = _coordinate_pairs(df, row)
        item["coordinate_points"] = coordinates
        item["enlem"] = coordinates[0]["lat"] if coordinates else None
        item["boylam"] = coordinates[0]["lon"] if coordinates else None
        rows.append(item)
    return rows, mapping, []
