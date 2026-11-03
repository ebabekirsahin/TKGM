import streamlit as st
import pandas as pd
from core.excel import read_excel, normalize_excel
from core.matching import match_records
from sources.loaders import load_spatial_upload
from sources.wfs import fetch_public_wfs
from sources.tkgm_public import lookup_parcel_by_coordinate
from sources.tkgm_cadastral import fetch_public_cadastral_parcels
from sources.arcgis_public import discover_public_parcel_features
from sources.curated_arcgis import fetch_curated_public_parcels
from core.normalize import norm
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
    auto_public_search = st.checkbox("Açık ArcGIS parsel kaynaklarını otomatik tara", value=True, help="Yalnızca herkese açık, kimlik doğrulamasız ve gerekli parsel/idari alanları içeren katmanlar kullanılır.")

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
tkgm_terms_ok = st.checkbox("TKGM açık Parsel Sorgu kullanım koşullarını kabul ediyorum; istekler servis limitlerine tabidir.", value=False)
coordinate_points = []
for row in normalized:
    for point_index, point in enumerate(row.get("coordinate_points") or [], start=1):
        coordinate_points.append({
            "lat": point["lat"], "lon": point["lon"],
            "il": row.get("il", ""), "ilce": row.get("ilce", ""),
            "mahalle": row.get("mahalle", ""),
            "ada_pafta": row.get("ada_pafta", ""), "parsel": row.get("parsel", ""),
            "excel_satir": row.get("excel_satir", ""), "point_index": point_index,
        })
has_coordinates = bool(coordinate_points)
if has_coordinates:
    st.success(f"Excel'den {len(coordinate_points):,} geçerli koordinat noktası okundu. Noktalar parsel eşleşmesinden bağımsız olarak haritada gösterilecek.")
else:
    st.info("Koordinat sütunu bulunamadı veya değerler geçersiz. Yine de Türkiye haritası açılacak.")

if st.button("Verileri eşleştir ve haritayı oluştur", type="primary"):
    features, source_errors = [], []
    if tkgm_terms_ok:
        target_names = {"manisa", "afyonkarahisar", "canakkale", "malatya", "adana"}
        target_rows = [row for row in normalized if norm(row.get("il")) in target_names]
        if target_rows:
            tkgm_bar = st.progress(0)
            tkgm_status = st.empty()
            def _show_tkgm_progress(done, total, current_row):
                tkgm_bar.progress(done / max(total, 1))
                tkgm_status.caption(f"TKGM sorgusu: {done:,} / {total:,} tekil taşınmaz")
            try:
                with st.spinner(f"TKGM üzerinden {len(target_rows):,} taşınmaz sorgulanıyor..."):
                    cadastral_features, cadastral_notes = fetch_public_cadastral_parcels(
                        target_rows, progress_callback=_show_tkgm_progress
                    )
                features.extend(cadastral_features)
                source_errors.extend(cadastral_notes)
                tkgm_status.empty()
            except Exception as exc:
                source_errors.append(f"TKGM ada/parsel sorgusu: {exc}")
    else:
        st.info("TKGM ada/parsel sorgusu, kullanım koşulları onaylanmadığı için atlandı.")
    for uploaded in spatial_files or []:
        try: features.extend(load_spatial_upload(uploaded))
        except Exception as exc: source_errors.append(f"{uploaded.name}: {exc}")
    if wfs_url.strip() and wfs_layer.strip():
        try: features.extend(fetch_public_wfs(wfs_url.strip(), wfs_layer.strip(), int(wfs_limit)))
        except Exception as exc: source_errors.append(f"WFS: {exc}")
    # Curated municipal/TKGM public services are queried directly using the
    # uploaded cadastral keys; catalogue search remains a secondary discovery path.
    with st.spinner("Doğrudan açık belediye/TKGM parsel servisleri sorgulanıyor..."):
        try:
            curated, curated_notes = fetch_curated_public_parcels(normalized, max_features=15000)
            features.extend(curated)
            st.info(f"Doğrudan açık servislerden {len(curated):,} aday parsel geometrisi alındı. Kaynak kapsamları sınırlıdır.")
            source_errors.extend(curated_notes)
        except Exception as exc:
            source_errors.append(f"Doğrudan açık servis sorgusu: {exc}")

    if auto_public_search:
        with st.spinner("Herkese açık ArcGIS parsel katalogları taranıyor..."):
            try:
                discovered = discover_public_parcel_features(normalized, max_items=8, max_records_per_layer=3000)
                features.extend(discovered)
                st.info(f"Otomatik açık veri kataloğundan {len(discovered):,} geometri kaydı alındı. Bu sayı Türkiye genelindeki toplam parsel sayısı değildir.")
            except Exception as exc:
                source_errors.append(f"Otomatik açık veri keşfi: {exc}")

    # TKGM public endpoint is coordinate -> parcel only. Never geocode a neighborhood
    # centroid and pretend it identifies the user's parcel.
    if has_coordinates and tkgm_terms_ok:
        progress = st.progress(0)
        target_names = {"manisa", "afyonkarahisar", "canakkale", "malatya", "adana"}
        coordinate_rows = [r for r in normalized if r.get("enlem") is not None and r.get("boylam") is not None and norm(r.get("il")) not in target_names]
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
                if all(a and b and norm(a)==norm(b) for a,b in checks):
                    ada = get_prop(props,"ada") or get_prop(props,"ada_pafta")
                    if ada and norm(row["ada_pafta"]) == norm(ada):
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
        st.warning("Bu Excel'in kapsadığı il/ilçelerde şu anda erişilebilir açık parsel geometrisi bulunamadı. Koordinat eklemeniz gerekmiyor; aşağıda her kaynağın neden sonuç vermediğini inceleyebilirsiniz.")
    with st.spinner(f"{len(features):,} geometri kaydı eşleştiriliyor..."):
        results, matched_features = match_records(normalized, features)
    st.session_state["results"] = results
    st.session_state["matched_features"] = matched_features
    st.session_state["source_diagnostics"] = source_errors
    st.session_state["source_feature_count"] = len(features)

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
from streamlit_folium import st_folium
st_folium(build_map(matched, coordinate_points=coordinate_points),
          use_container_width=True, height=680, returned_objects=[])
if not matched and coordinate_points:
    st.info("Mavi işaretçiler Excel koordinatlarını gösterir. Henüz doğrulanmış parsel poligonu bulunmaması haritanın açılmasını engellemez.")
elif not matched:
    st.warning("Parsel geometrisi bulunamadı. Türkiye taban haritası yine de gösteriliyor.")
st.subheader("Eşleştirme sonuçları")
statuses = ["Bulundu","Doğrulanmalı","Bulunamadı"]
selected = st.multiselect("Durum filtresi", statuses, default=statuses)
st.dataframe(results[results["Durum"].isin(selected)], use_container_width=True, hide_index=True)
st.download_button("📥 Sonuç Excel'ini indir", data=make_excel(results), file_name="tasinmaz_sonuclari.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
st.caption("TKGM koordinat servisi kamuya açık web istemcisinin koordinat sorgusudur; resmî toplu ada/parsel API'si olarak sunulmamaktadır. Kullanım koşulları ve servis limitleri geçerlidir.")
