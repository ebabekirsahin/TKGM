# Türkiye Taşınmaz Haritası

Streamlit uygulaması; Excel'deki il, ilçe, mahalle, ada/pafta ve parsel kayıtlarını kullanıcının sağladığı herkese açık coğrafi veriyle eşleştirir. Gerçek geometri bulunursa parsel sınırı ve merkez koordinatı haritada gösterilir. Geometri yoksa koordinat üretilmez.

## Önemli veri kapsamı
Bu proje TKGM'nin özel/iç servislerini, CAPTCHA aşmayı veya yetkisiz erişimi kullanmaz. Türkiye genelindeki tüm kadastro parsellerini kapsayan, sınırsız ve herkese açık resmî bir TKGM API'si varmış gibi davranmaz. Açık WFS/GeoJSON katmanları yalnızca kendi gerçek kapsamları ve lisansları ölçüsünde kullanılabilir. Belediyeye ait bir servis tüm Türkiye'yi kapsamayabilir.

## Kurulum
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
- Repository: ebatabekirsahin/TKGM (GitHub'daki gerçek repository adı/owner kontrol edilmelidir)
- Branch: main
- Main file: app.py

## Girdi
Excel (.xlsx) zorunlu sütunları: İL, İlçe, Mahalle, ADA-PAFTA, PARSEL.
İsteğe bağlı coğrafi kaynaklar: GeoJSON, KML veya ZIP içinde Shapefile. GeoJSON koordinatları WGS84/EPSG:4326 olmalıdır. Shapefile ZIP içinde .shp, .shx, .dbf ve .prj dosyaları bulunmalıdır.

Uygulama ayrıca herkese açık WFS 1.x/2.0 GetFeature uç noktası ve katman adı kabul eder. Servisin JSON GeoJSON çıktısı vermesi gerekir. WFS'nin tüm katmanı indirmesi performans, kota ve servis koşullarına bağlıdır; azami kayıt sınırı vardır.

## Eşleştirme
- Türkçe karakterler ve boşluk/noktalama normalize edilir.
- İl, ilçe, mahalle, ada/pafta ve parsel alanları karşılaştırılır.
- Birden fazla eşleşme varsa kayıt doğrulama bekler.
- Kaynakta gerekli öznitelikler yoksa eşleşme kesin sayılmaz.
- Polygon/MultiPolygon geometrilerinden temsilî iç nokta hesaplanır.

## Gizlilik ve lisans
Yalnızca indirme/kullanım şartlarına uygun açık veri kaynaklarını kullanın. Kaynak URL'si ve lisansını kayıt altına alın. Excel dosyaları uygulama oturumunda işlenir; kalıcı depolama yapılandırılmadı.
