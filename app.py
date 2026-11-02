# app.py
# Kurulum:
# pip install streamlit pandas openpyxl folium streamlit-folium
#
# Çalıştırma:
# streamlit run app.py
#
# Önemli:
# TKGM'nin ülke çapında ada/parsel sorgusu için herkese açık, resmî olarak
# desteklendiği doğrulanmış bir geliştirici API'si bulunmadığından bu uygulama
# TKGM'nin iç servislerini çağırmaz. TKGM Parsel Sorgu'dan veya yetkili veri
# sağlayıcınızdan hukuka uygun biçimde indirdiğiniz GeoJSON/KML dosyasını
# eşleştirme kaynağı olarak kullanır. GeoJSON koordinatları EPSG:4326 olmalıdır.

import io
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Tuple

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen, MiniMap
from streamlit_folium import st_folium


st.set_page_config(
    page_title="Türkiye Taşınmaz Haritası",
    page_icon="🗺️",
    layout="wide",
)

REQUIRED_COLUMNS = {
    "il": ["il", "ili", "province", "city"],
    "ilce": ["ilce", "ilçesi", "ilcesi", "district", "county"],
    "mahalle": ["mahalle", "mahalle adı", "mahalle adi", "koy", "köy", "neighborhood"],
    "ada_pafta": ["ada-pafta", "ada pafta", "adapafta", "ada", "pafta", "ada_no", "adano"],
    "parsel": ["parsel", "parsel no", "parsel_no", "parcel", "parcelno"],
}

PROPERTY_ALIASES = {
    "il": ["il", "il_adi", "iladi", "province", "city"],
    "ilce": ["ilce", "ilçe", "ilce_adi", "ilceadi", "district"],
    "mahalle": ["mahalle", "mahalle_adi", "mahalleadi", "koy", "köy", "neighborhood"],
    "ada": ["ada", "ada_no", "adano", "adanumarasi", "block", "blockno"],
    "pafta": ["pafta", "pafta_no", "paftano", "sheet"],
    "ada_pafta": ["ada_pafta", "adapafta", "ada-pafta", "ada pafta"],
    "parsel": ["parsel", "parsel_no", "parselno", "parcel", "parcelno"],
}


def norm(value: Any) -> str:
    """Türkçe karakterleri ve noktalama farklarını normalize eder."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().casefold()
    text = text.translate(str.maketrans({"ı": "i", "İ": "i", "ş": "s", "ğ": "g",
                                         "ü": "u", "ö": "o", "ç": "c"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text)


def clean_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    # Excel'in sayısal hücreleri 123.0 olarak getirmesini önle.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def find_columns(df: pd.DataFrame) -> Tuple[Dict[str, str], List[str]]:
    normalized = {norm(col): col for col in df.columns}
    found: Dict[str, str] = {}
    missing: List[str] = []
    for logical, aliases in REQUIRED_COLUMNS.items():
        match = None
        for alias in aliases:
            key = norm(alias)
            if key in normalized:
                match = normalized[key]
                break
        if match is None:
            missing.append(logical)
        else:
            found[logical] = match
    return found, missing


def property_value(properties: Dict[str, Any], logical: str) -> str:
    normalized = {norm(k): v for k, v in properties.items()}
    for alias in PROPERTY_ALIASES[logical]:
        key = norm(alias)
        if key in normalized:
            return clean_value(normalized[key])
    return ""


def get_geometry_coords(geometry: Dict[str, Any]) -> List[Tuple[float, float]]:
    """GeoJSON geometrisinden (lon, lat) koordinatlarını toplar."""
    result: List[Tuple[float, float]] = []

    def walk(obj: Any):
        if isinstance(obj, (list, tuple)):
            if len(obj) >= 2 and isinstance(obj[0], (int, float)) and isinstance(obj[1], (int, float)):
                lon, lat = float(obj[0]), float(obj[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    result.append((lon, lat))
            else:
                for child in obj:
                    walk(child)

    if geometry and "coordinates" in geometry:
        walk(geometry["coordinates"])
    elif geometry and geometry.get("type") == "GeometryCollection":
        for child in geometry.get("geometries", []):
            result.extend(get_geometry_coords(child))
    return result


def geometry_center(geometry: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    coords = get_geometry_coords(geometry)
    if not coords:
        return None
    # Harita üzerindeki bilgilendirme işaretçisi için koordinatların ortalaması.
    # Parselin sınır geometrisi ayrıca gerçek GeoJSON geometrisi olarak çizilir.
    lon = sum(p[0] for p in coords) / len(coords)
    lat = sum(p[1] for p in coords) / len(coords)
    return lat, lon


def load_geojson(uploaded_file) -> List[Dict[str, Any]]:
    raw = json.load(uploaded_file)
    if raw.get("type") == "FeatureCollection":
        features = raw.get("features", [])
    elif raw.get("type") == "Feature":
        features = [raw]
    else:
        raise ValueError("GeoJSON dosyası Feature veya FeatureCollection olmalıdır.")
    output = []
    for feature in features:
        if not isinstance(feature, dict) or not feature.get("geometry"):
            continue
        output.append({
            "properties": feature.get("properties") or {},
            "geometry": feature["geometry"],
            "source_type": "GeoJSON",
        })
    return output


def parse_kml_coordinates(text: str) -> List[List[List[float]]]:
    coords = []
    for token in text.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                coords.append([float(parts[0]), float(parts[1])])
            except ValueError:
                continue
    return coords


def load_kml(uploaded_file) -> List[Dict[str, Any]]:
    root = ET.fromstring(uploaded_file.getvalue())
    output = []
    for placemark in root.iter():
        if placemark.tag.split("}")[-1] != "Placemark":
            continue
        props: Dict[str, Any] = {}
        name_el = next((e for e in placemark if e.tag.split("}")[-1] == "name"), None)
        if name_el is not None and name_el.text:
            props["name"] = name_el.text.strip()

        for el in placemark.iter():
            tag = el.tag.split("}")[-1]
            if tag == "Data":
                key = el.attrib.get("name", "")
                value_el = next((x for x in el if x.tag.split("}")[-1] == "value"), None)
                if key and value_el is not None:
                    props[key] = value_el.text or ""
            elif tag == "SimpleData":
                key = el.attrib.get("name", "")
                if key:
                    props[key] = el.text or ""

        polygons = []
        points = []
        for el in placemark.iter():
            tag = el.tag.split("}")[-1]
            if tag == "coordinates" and el.text:
                parsed = parse_kml_coordinates(el.text)
                if not parsed:
                    continue
                # KML Polygon coordinates normally contain a closed ring.
                parent_tags = []
                if len(parsed) >= 4:
                    polygons.append([parsed])
                else:
                    points.extend(parsed)

        geometry = None
        if polygons:
            geometry = {"type": "MultiPolygon",
                        "coordinates": [[ring for ring in polygon] for polygon in polygons]}
        elif points:
            if len(points) == 1:
                geometry = {"type": "Point", "coordinates": points[0]}
            else:
                geometry = {"type": "LineString", "coordinates": points}
        if geometry:
            output.append({"properties": props, "geometry": geometry, "source_type": "KML"})
    return output


def load_reference_file(uploaded_file) -> List[Dict[str, Any]]:
    name = uploaded_file.name.lower()
    if name.endswith(".geojson") or name.endswith(".json"):
        return load_geojson(uploaded_file)
    if name.endswith(".kml"):
        return load_kml(uploaded_file)
    raise ValueError("Desteklenmeyen dosya. Lütfen .geojson, .json veya .kml yükleyin.")


def make_record_key(values: Dict[str, str]) -> Tuple[str, ...]:
    return tuple(norm(values.get(k, "")) for k in ("il", "ilce", "mahalle", "ada_pafta", "parsel"))


def feature_matches(row: Dict[str, str], feature: Dict[str, Any]) -> Tuple[bool, str]:
    props = feature["properties"]
    p_il = property_value(props, "il")
    p_ilce = property_value(props, "ilce")
    p_mahalle = property_value(props, "mahalle")
    p_parsel = property_value(props, "parsel")
    p_ada = property_value(props, "ada")
    p_pafta = property_value(props, "pafta")
    p_ada_pafta = property_value(props, "ada_pafta")

    # Parsel numarası olmadan eşleşme yapılmaz.
    if not row["parsel"] or not p_parsel or norm(row["parsel"]) != norm(p_parsel):
        return False, ""

    # İl/ilçe/mahalle alanları kaynakta varsa mutlaka uyuşmalıdır.
    for row_key, prop_value in (("il", p_il), ("ilce", p_ilce), ("mahalle", p_mahalle)):
        if prop_value and norm(row[row_key]) != norm(prop_value):
            return False, ""

    if not row["ada_pafta"]:
        return False, ""

    wanted = norm(row["ada_pafta"])
    candidates = [norm(v) for v in (p_ada, p_pafta, p_ada_pafta) if v]
    if wanted not in candidates:
        return False, ""

    # Kaynakta idari alanların tamamı yoksa eşleşme şüpheli kabul edilir.
    completeness = sum(bool(x) for x in (p_il, p_ilce, p_mahalle))
    if completeness < 3:
        return True, "Kısmi özellik eşleşmesi; idari alanlar kontrol edilmeli"
    return True, "Tam özellik eşleşmesi"


def build_result(row: Dict[str, str], features: List[Dict[str, Any]]) -> Dict[str, Any]:
    matches = []
    for feature in features:
        ok, note = feature_matches(row, feature)
        if ok:
            matches.append((feature, note))

    if len(matches) == 1:
        feature, note = matches[0]
        center = geometry_center(feature["geometry"])
        if center is None:
            return {"Durum": "Doğrulanmalı", "Enlem": None, "Boylam": None,
                    "Geometri": None, "Kaynak": feature["source_type"],
                    "Açıklama": "Eşleşen kayıtta geçerli koordinat bulunamadı."}
        return {"Durum": "Bulundu" if note.startswith("Tam") else "Doğrulanmalı",
                "Enlem": center[0], "Boylam": center[1],
                "Geometri": feature["geometry"], "Kaynak": feature["source_type"],
                "Açıklama": note}
    if len(matches) > 1:
        return {"Durum": "Doğrulanmalı", "Enlem": None, "Boylam": None,
                "Geometri": None, "Kaynak": "", 
                "Açıklama": f"{len(matches)} geometri eşleşti; tekil kayıt belirlenemedi."}
    return {"Durum": "Bulunamadı", "Enlem": None, "Boylam": None,
            "Geometri": None, "Kaynak": "",
            "Açıklama": "Yüklenen GeoJSON/KML içinde eşleşen parsel bulunamadı."}


def main():
    st.title("🗺️ Türkiye Taşınmaz Haritası")
    st.write("Excel taşınmaz listenizi, yüklediğiniz gerçek parsel GeoJSON/KML verisiyle eşleştirin.")
    st.info(
        "Bu uygulama TKGM'nin kapalı/izin gerektiren servislerini çağırmaz. "
        "TKGM veri paylaşımı düzenlemesinde ülke çapında veri sorgulaması için protokol veya "
        "sözleşme şartı öngörülür. Resmî erişim yetkiniz varsa kurumunuzun sağladığı veri "
        "çıktısını kullanın. TKGM Parsel Sorgu'dan indirilen KML/GeoJSON dosyaları da "
        "uygun kullanım koşulları çerçevesinde yüklenebilir."
    )
    st.markdown(
        "Resmî kaynaklar: [TKGM Parsel Sorgulama](https://www.tkgm.gov.tr/e-hizmetler/"
        "sik-kullanilanlar/parsel-sorgulama) · "
        "[Tapu ve Kadastro Verilerinin Paylaşımı Hakkında Yönetmelik]"
        "(https://www.tkgm.gov.tr/duyurular/tapu-ve-kadastro-verilerinin-paylasimi-hakkinda-yonetmelik)"
    )

    with st.sidebar:
        st.header("1. Dosyaları yükleyin")
        excel_file = st.file_uploader("Taşınmaz Excel dosyası", type=["xlsx"])
        spatial_file = st.file_uploader(
            "Parsel geometrisi (GeoJSON veya KML)",
            type=["geojson", "json", "kml"],
            help="Parsel öznitelikleri il, ilçe, mahalle, ada/pafta ve parsel alanlarını içermelidir.",
        )
        st.caption("GeoJSON koordinat sistemi EPSG:4326 (WGS84) olmalıdır. "
                   "Başka koordinat sistemindeki veriler otomatik dönüştürülmez.")

    if excel_file is None:
        st.warning("Başlamak için Excel dosyanızı yükleyin.")
        st.stop()

    try:
        excel_file.seek(0)
        workbook = pd.ExcelFile(excel_file)
        sheet = st.selectbox("Excel sayfası", workbook.sheet_names)
        df = pd.read_excel(workbook, sheet_name=sheet, dtype=object)
    except Exception as exc:
        st.error(f"Excel dosyası okunamadı: {exc}")
        st.stop()

    columns, missing = find_columns(df)
    if missing:
        labels = {"il": "İL", "ilce": "İlçe", "mahalle": "Mahalle",
                  "ada_pafta": "ADA-PAFTA", "parsel": "PARSEL"}
        st.error("Excel dosyasında zorunlu sütunlar eksik: " +
                 ", ".join(labels[x] for x in missing))
        st.write("Bulunan sütunlar:", ", ".join(map(str, df.columns)))
        st.stop()

    st.subheader("Excel önizlemesi")
    st.dataframe(df.head(10), use_container_width=True)

    if spatial_file is None:
        st.warning(
            "Henüz parsel geometri dosyası yüklenmedi. TKGM'ye otomatik sorgu yapılmayacak; "
            "bu nedenle koordinat üretilmez. Bir GeoJSON/KML yüklediğinizde eşleştirme yapılabilir."
        )
        st.stop()

    if st.button("Taşınmazları eşleştir ve haritada göster", type="primary"):
        try:
            spatial_file.seek(0)
            features = load_reference_file(spatial_file)
            if not features:
                st.error("Dosyada kullanılabilir geometri bulunamadı.")
                st.stop()
        except Exception as exc:
            st.error(f"GeoJSON/KML okunamadı: {exc}")
            st.stop()

        output_rows = []
        map_features = []
        progress = st.progress(0)
        status = st.empty()
        total = len(df)

        for index, (_, excel_row) in enumerate(df.iterrows()):
            row = {key: clean_value(excel_row[col]) for key, col in columns.items()}
            missing_values = [k for k, v in row.items() if not v]
            result = build_result(row, features)
            if missing_values and result["Durum"] == "Bulundu":
                result["Durum"] = "Doğrulanmalı"
                result["Açıklama"] = "Excel satırında eksik alan var: " + ", ".join(missing_values)

            output = {
                "İL": row["il"], "İlçe": row["ilce"], "Mahalle": row["mahalle"],
                "ADA-PAFTA": row["ada_pafta"], "PARSEL": row["parsel"],
                "Durum": result["Durum"], "Enlem": result["Enlem"],
                "Boylam": result["Boylam"], "Geometri Kaynağı": result["Kaynak"],
                "Açıklama": result["Açıklama"],
            }
            output_rows.append(output)

            if result["Geometri"] is not None:
                map_features.append({
                    "type": "Feature",
                    "geometry": result["Geometri"],
                    "properties": {
                        "İL": row["il"], "İlçe": row["ilce"], "Mahalle": row["mahalle"],
                        "ADA-PAFTA": row["ada_pafta"], "PARSEL": row["parsel"],
                        "Durum": result["Durum"], "Açıklama": result["Açıklama"],
                    },
                })
            progress.progress((index + 1) / max(total, 1))
            status.text(f"{index + 1}/{total} kayıt işlendi")

        result_df = pd.DataFrame(output_rows)
        st.session_state["result_df"] = result_df
        st.session_state["map_features"] = map_features
        st.session_state["reference_count"] = len(features)
        st.success("Eşleştirme tamamlandı.")

    if "result_df" not in st.session_state:
        st.caption("Eşleştirmeyi başlatmak için yukarıdaki butona basın.")
        st.stop()

    result_df = st.session_state["result_df"]
    found = int((result_df["Durum"] == "Bulundu").sum())
    not_found = int((result_df["Durum"] == "Bulunamadı").sum())
    verify = int((result_df["Durum"] == "Doğrulanmalı").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam taşınmaz", len(result_df))
    c2.metric("Bulunan", found)
    c3.metric("Bulunamayan", not_found)
    c4.metric("Doğrulanacak", verify)

    st.subheader("Türkiye haritası")
    map_features = st.session_state.get("map_features", [])
    if map_features:
        all_coords = []
        for feature in map_features:
            all_coords.extend(get_geometry_coords(feature["geometry"]))
        if all_coords:
            center = [sum(p[1] for p in all_coords) / len(all_coords),
                      sum(p[0] for p in all_coords) / len(all_coords)]
        else:
            center = [39.0, 35.0]
        fmap = folium.Map(location=center, zoom_start=6, tiles="OpenStreetMap",
                          control_scale=True)
        Fullscreen(position="topright").add_to(fmap)
        MiniMap(toggle_display=True).add_to(fmap)

        for feature in map_features:
            props = feature["properties"]
            popup_html = (
                "<div style='min-width:220px'>"
                f"<b>İl:</b> {props['İL']}<br>"
                f"<b>İlçe:</b> {props['İlçe']}<br>"
                f"<b>Mahalle:</b> {props['Mahalle']}<br>"
                f"<b>Ada-Pafta:</b> {props['ADA-PAFTA']}<br>"
                f"<b>Parsel:</b> {props['PARSEL']}<br>"
                f"<b>Durum:</b> {props['Durum']}<br>"
                f"<b>Not:</b> {props['Açıklama']}"
                "</div>"
            )
            center_point = geometry_center(feature["geometry"])
            folium.GeoJson(
                feature,
                name=f"{props['İL']} / {props['İlçe']} / {props['ADA-PAFTA']}-{props['PARSEL']}",
                style_function=lambda _f, status=props["Durum"]: {
                    "color": "#16803c" if status == "Bulundu" else "#d97706",
                    "weight": 3, "fillOpacity": 0.18,
                },
                tooltip=f"{props['İL']} - {props['İlçe']} - {props['Mahalle']} | "
                        f"Ada/Pafta: {props['ADA-PAFTA']} | Parsel: {props['PARSEL']}",
                popup=folium.Popup(popup_html, max_width=350),
            ).add_to(fmap)
            if center_point:
                folium.CircleMarker(
                    location=center_point, radius=4, color="#173f5f",
                    fill=True, fill_opacity=0.9,
                    tooltip=f"{props['İL']} / {props['İlçe']} - {props['PARSEL']}",
                    popup=folium.Popup(popup_html, max_width=350),
                ).add_to(fmap)

        folium.LayerControl(collapsed=True).add_to(fmap)
        st_folium(fmap, use_container_width=True, height=650, returned_objects=[])
    else:
        st.warning("Haritada gösterilecek doğrulanmış geometri bulunamadı. "
                   "Sahte nokta oluşturulmadı.")

    st.subheader("Eşleştirme sonuçları")
    status_filter = st.multiselect(
        "Duruma göre filtrele",
        options=["Bulundu", "Bulunamadı", "Doğrulanmalı"],
        default=["Bulundu", "Bulunamadı", "Doğrulanmalı"],
    )
    st.dataframe(result_df[result_df["Durum"].isin(status_filter)],
                 use_container_width=True, hide_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result_df.to_excel(writer, index=False, sheet_name="Tasınmaz Sonuçları")
        summary = pd.DataFrame({
            "Gösterge": ["Toplam", "Bulundu", "Bulunamadı", "Doğrulanmalı"],
            "Adet": [len(result_df), found, not_found, verify],
        })
        summary.to_excel(writer, index=False, sheet_name="Özet")
    output.seek(0)
    st.download_button(
        "📥 Koordinatlı sonuç Excel'ini indir",
        data=output.getvalue(),
        file_name="tasinmaz_eslestirme_sonuclari.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    st.caption(
        "Not: TKGM Parsel Sorgu verileri bilgilendirme amaçlıdır. Uygulamanın eşleştirme "
        "sonucu resmî kadastro belgesi veya mülkiyet doğrulaması yerine geçmez. "
        "Kısmi eşleşmeler ve aynı ada/parsel numarasına ait birden fazla geometri "
        "mutlaka kullanıcı tarafından kontrol edilmelidir."
    )


if __name__ == "__main__":
    main()
