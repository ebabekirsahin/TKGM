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

def normalize_excel(df):
    lookup = {norm(c): c for c in df.columns}
    mapping = {}
    missing = []
    for key, aliases in ALIASES.items():
        col = next((lookup[norm(a)] for a in aliases if norm(a) in lookup), None)
        if col is None: missing.append(LABELS[key])
        else: mapping[key] = col
    if missing: return [], mapping, missing
    rows = []
    for idx, row in df.iterrows():
        item = {key: clean(row[col]) for key,col in mapping.items()}
        item["excel_satir"] = int(idx)+2
        rows.append(item)
    return rows, mapping, []
