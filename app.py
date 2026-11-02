import io
import streamlit as st
import pandas as pd
from core.excel import read_excel, normalize_excel
from core.matching import match_records
from sources.loaders import load_spatial_upload
from sources.wfs import fetch_public_wfs
from map_view.render import build_map
from reports.export import make_excel

st.set_page_config(page_title="Türkiye Taşınmaz Haritası", page_icon="🗺️", layout="wide")
st.title("🗺️ Türkiye Taşınmaz Envanteri")
st.caption("Excel kayıtlarını yalnızca sağladığınız herkese açık coğrafi verilerle eşleştirir; bulunmayan geometriyi üretmez.")

with st.sidebar:
    st.header("Veri yükleme")
    excel_file = st.file_uploader("Taşınmaz Excel'i (.xlsx)", type=["xlsx"])
    spatial_files = st.file_uploader("Açık parsel verisi (.geojson, .json, .kml, .zip)", type=["geojson","json","kml","zip"], accept_multiple_files=True)
    st.divider()
    st.subheader("İsteğe bağlı açık WFS")
    wfs_url = st.text_input("Herkese açık WFS adresi", placeholder="https://.../wfs")
    wfs_layer = st.text_input("Katman adı (typeName)", placeholder="workspace:parcel_layer")
    wfs_limit = st.number_input("Azami WFS kayıt sayısı", min_value=1, max_value=100000, value=10000, step=1000)
    st.caption("Yalnızca kullanım koşulları izin veren, kimlik doğrulama/CAPTCHA gerektirmeyen açık servisleri kullanın. Uygulama TKGM özel servislerini çağırmaz.")

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

if len(normalized) > 10000:
    st.warning("10.000 üzeri kayıt yüklediniz. İşlem süresi ve bellek ihtiyacı artabilir.")

if st.button("Verileri eşleştir ve haritayı oluştur", type="primary"):
    features = []
    source_errors = []
    for uploaded in spatial_files or []:
        try:
            features.extend(load_spatial_upload(uploaded))
        except Exception as exc:
            source_errors.append(f"{uploaded.name}: {exc}")
    if wfs_url.strip() and wfs_layer.strip():
        try:
            features.extend(fetch_public_wfs(wfs_url.strip(), wfs_layer.strip(), int(wfs_limit)))
        except Exception as exc:
            source_errors.append(f"WFS: {exc}")
    if source_errors:
        for msg in source_errors:
            st.warning(msg)
    if not features:
        st.error("Eşleştirilecek gerçek geometri kaynağı yok. Açık GeoJSON/KML/ZIP veya herkese açık WFS sağlamalısınız. Koordinat uydurulmadı.")
        st.stop()
    with st.spinner(f"{len(features):,} geometri kaydı hazırlanıyor ve {len(normalized):,} taşınmaz eşleştiriliyor..."):
        results, matched_features = match_records(normalized, features)
    st.session_state["results"] = results
    st.session_state["matched_features"] = matched_features
    st.session_state["source_feature_count"] = len(features)

if "results" not in st.session_state:
    st.info("Veri kaynağını ekledikten sonra eşleştirme butonuna basın.")
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
    fmap = build_map(matched)
    from streamlit_folium import st_folium
    st_folium(fmap, use_container_width=True, height=680, returned_objects=[])
else:
    st.warning("Gerçek geometriyle eşleşen kayıt bulunamadı; haritaya sahte nokta eklenmedi.")

st.subheader("Eşleştirme sonuçları")
filter_status = st.multiselect("Durum filtresi", ["Bulundu","Doğrulanmalı","Bulunamadı"], default=["Bulundu","Doğrulanmalı","Bulunamadı"])
st.dataframe(results[results["Durum"].isin(filter_status)], use_container_width=True, hide_index=True)
st.download_button("📥 Sonuç Excel'ini indir", data=make_excel(results), file_name="tasinmaz_sonuclari.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
st.caption("Kapsam uyarısı: Türkiye çapında bütün parselleri kapsayan, sınırsız ve herkesin kullanımına açık resmî bir TKGM parsel geometri API'si varsayılmamıştır. Sonuç kapsamı yüklenen açık verilerin kapsamıyla sınırlıdır. Veriler resmî kadastro belgesi veya mülkiyet doğrulaması değildir.")
