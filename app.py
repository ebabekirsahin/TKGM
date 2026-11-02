import streamlit as st
import pandas as pd
from core.excel import read_excel, normalize_excel
from core.matching import match_records
from sources.loaders import load_spatial_upload
from sources.wfs import fetch_public_wfs
from sources.tkgm_public import lookup_parcel_by_coordinate
from map_view.render import build_map
from reports.export import make_excel

st.set_page_config(page_title="Türkiye Taşınmaz Haritası", page_icon="🗺️", layout="wide")
st.title("🗺️ Türkiye Taşınmaz Envanteri")
st.caption("Gerçek parsel geometrileri yalnızca erişilebilen veri kaynaklarından alınır; koordinat tahmin edilmez.")

with st.sidebar:
    st.header("Veri yükleme")
    excel_file = st.file_uploader("Taşınmaz Excel'i (.xlsx)", type=["xlsx"])
    spatial_files = st.file_uploader("Açık parsel verisi (.geojson, .json, .kml, .zip)", type=["geojson","json","kml","zip"], accept_multiple_files=True)
    st.divider()
    st.subheader("İsteğe bağlı açık WFS")
    wfs_url = st.text_input("Herkese açık WFS adresi", placeholder="https://.../wfs")
    wfs_layer = st.text_input("Katman adı (typeName)", placeholder="workspace:parcel_layer")
    wfs_limit = st.number_input("Azami WFS kayıt sayısı", min_value=1, max_value=100000, value=10000, step=1000)

if not excel_file:
    st.info("Başlamak için Excel dosyanızı yükleyin.")
    st.stop()
try:
    df = read_excel(excel_file)
    normalized, column_map, errors = normalize_excel(df)
except Exception as exc:
    st.error(f"Excel okunamadı: {exc}")
    st.stop()
if errors:
    st.error("Eksik zorunlu sütunlar: " + ", ".join(errors))
    st.caption("Beklenen sütunlar: İL, İlçe, Mahalle, ADA-PAFTA, PARSEL")
    st.stop()

st.subheader("Excel önizlemesi")
st.dataframe(df.head(20), use_container_width=True)
st.write(f"Toplam kayıt: **{len(normalized):,}**")
has_coordinates = all("enlem" in r and "boylam" in r for r in normalized)
if has_coordinates:
    valid_coords = sum(r.get("enlem") is not None and r.get("boylam") is not None for r in normalized)
    st.info(f"Excel'de {valid_coords:,} satırda geçerli ENLEM/BOYLAM bulundu. Bu koordinatlar TKGM'nin herkese açık koordinat sorgusunda kullanılabilir.")
else:
    st.warning("Excel'inizde ENLEM ve BOYLAM sütunları yok. TKGM'nin herkese açık koordinat servisi koordinattan parsele gider; yalnızca ada/parsel bilgisinden koordinat bulmaz. Bu beş sütunla otomatik TKGM sorgusu yapılamaz.")

if st.button("Verileri eşleştir ve haritayı oluştur", type="primary"):
    features, source_errors = [], []
    for uploaded in spatial_files or []:
        try: features.extend(load_spatial_upload(uploaded))
        except Exception as exc: source_errors.append(f"{uploaded.name}: {exc}")
    if wfs_url.strip() and wfs_layer.strip():
        try: features.extend(fetch_public_wfs(wfs_url.strip(), wfs_layer.strip(), int(wfs_limit)))
        except Exception as exc: source_errors.append(f"WFS: {exc}")

    # TKGM public endpoint is coordinate -> parcel only. Never geocode a neighborhood
    # centroid and pretend it identifies the user's parcel.
    if has_coordinates:
        progress = st.progress(0)
        coordinate_rows = [r for r in normalized if r.get("enlem") is not None and r.get("boylam") is not None]
        for i, row in enumerate(coordinate_rows):
            try:
                feature = lookup_parcel_by_coordinate(row["enlem"], row["boylam"])
                props = feature.get("properties") or {}
                # Keep only results whose returned cadastral identifiers match the Excel row.
                from core.matching import get_prop
                checks = [
                    (row["il"], get_prop(props,"il")),
                    (row["ilce"], get_prop(props,"ilce")),
                    (row["mahalle"], get_prop(props,"mahalle")),
                    (row["parsel"], get_prop(props,"parsel")),
                ]
                if all(a and b and __import__("core.normalize",fromlist=["norm"]).norm(a)==__import__("core.normalize",fromlist=["norm"]).norm(b) for a,b in checks):
                    ada = get_prop(props,"ada") or get_prop(props,"ada_pafta")
                    if ada and __import__("core.normalize",fromlist=["norm"]).norm(row["ada_pafta"]) == __import__("core.normalize",fromlist=["norm"]).norm(ada):
                        features.append(feature)
                    else:
                        source_errors.append(f"Excel satırı {row['excel_satir']}: TKGM koordinat sonucu ada/pafta ile doğrulanamadı.")
                else:
                    source_errors.append(f"Excel satırı {row['excel_satir']}: Koordinatın TKGM sonucu Excel'deki idari/parsel bilgileriyle eşleşmedi.")
            except Exception as exc:
                source_errors.append(f"Excel satırı {row['excel_satir']}: TKGM koordinat sorgusu: {exc}")
            progress.progress((i+1)/max(len(coordinate_rows),1))
    if source_errors:
        with st.expander(f"Kaynak / sorgu notları ({len(source_errors)})"):
            for msg in source_errors: st.warning(msg)
    if not features:
        st.error("Gerçek parsel geometrisi elde edilemedi. Beş sütunlu Excel tek başına yeterli değildir: TKGM'nin herkese açık servisi koordinat -> parsel sorgusu yapar; ada/parsel -> koordinat sorgusu e-Devlet yetkilendirmesi gerektirir. ENLEM/BOYLAM sütunları ekleyin veya lisansı uygun açık geometri/WFS kaynağı sağlayın. Mahalle merkezi gibi yaklaşık noktalar parsel konumu olarak kullanılmadı.")
        st.stop()
    with st.spinner(f"{len(features):,} geometri kaydı eşleştiriliyor..."):
        results, matched_features = match_records(normalized, features)
    st.session_state["results"] = results
    st.session_state["matched_features"] = matched_features

if "results" not in st.session_state:
    st.info("Gerçek veri kaynağı ekledikten sonra eşleştirme butonuna basın.")
    st.stop()
results = st.session_state["results"]
matched = st.session_state["matched_features"]
found = int((results["Durum"] == "Bulundu").sum())
verify = int((results["Durum"] == "Doğrulanmalı").sum())
missing = int((results["Durum"] == "Bulunamadı").sum())
a,b,c,d = st.columns(4)
a.metric("Toplam taşınmaz", f"{len(results):,}")
b.metric("Bulundu", f"{found:,}")
c.metric("Doğrulanmalı", f"{verify:,}")
d.metric("Bulunamadı", f"{missing:,}")
st.subheader("Türkiye genelindeki taşınmazlar")
if matched:
    from streamlit_folium import st_folium
    st_folium(build_map(matched), use_container_width=True, height=680, returned_objects=[])
else:
    st.warning("Gerçek geometriyle eşleşen kayıt bulunamadı; sahte nokta eklenmedi.")
st.subheader("Eşleştirme sonuçları")
statuses = ["Bulundu","Doğrulanmalı","Bulunamadı"]
selected = st.multiselect("Durum filtresi", statuses, default=statuses)
st.dataframe(results[results["Durum"].isin(selected)], use_container_width=True, hide_index=True)
st.download_button("📥 Sonuç Excel'ini indir", data=make_excel(results), file_name="tasinmaz_sonuclari.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
st.caption("TKGM koordinat servisi kamuya açık web istemcisinin koordinat sorgusudur; resmî toplu ada/parsel API'si olarak sunulmamaktadır. Kullanım koşulları ve servis limitleri geçerlidir.")
