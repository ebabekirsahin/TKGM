# Türkiye Taşınmaz Haritası

Streamlit uygulaması; Excel'deki il, ilçe, mahalle, ada/pafta ve parsel kayıtlarını gerçek geometri kaynaklarıyla eşleştirir. Gerçek parsel geometrisi bulunmadan haritada tahmini nokta veya sınır oluşturmaz.

## TKGM herkese açık koordinat sorgusu

Uygulama, TKGM Parsel Sorgu web istemcisinin herkese açık koordinat-temelli sorgusunu `sources/tkgm_public.py` üzerinden çağırabilir.

**Önemli sınır:** Bu uç nokta koordinat → parsel sorgusudur. İl/ilçe/mahalle/ada/parsel metninden koordinat üretmez ve Türkiye çapında toplu ada-parsel sorgusu için resmî, sınırsız bir API değildir. Excel'e isteğe bağlı `ENLEM` ve `BOYLAM` sütunları (WGS84/EPSG:4326) eklendiğinde uygulama koordinatları sorgular; dönen idari/parsel kimlikleri Excel satırıyla eşleşmeden geometriyi kabul etmez. Mahalle merkezi veya yaklaşık koordinat kullanılmaz.

Servis yanıtı 401/403 veya 429 verirse işlem durdurulur. Kimlik doğrulama, CAPTCHA veya erişim kısıtlamaları aşılmaya çalışılmaz. Uç nokta resmî bir toplu veri API'si değil, kamuya açık web istemcisinin sorgu akışıdır; TKGM kullanım şartları ve servis politikaları geçerlidir.

## Diğer açık kaynaklar
- GeoJSON / KML / ZIP Shapefile yükleme
- Kullanım koşulları izin veren, kimlik doğrulamasız açık WFS (GeoJSON çıktısı)

Her kaynağın lisansı, kapsadığı coğrafya, güncellik tarihi ve kullanım koşulları ayrıca kontrol edilmelidir. Bir WFS katmanının tüm Türkiye'yi veya tüm parselleri kapsadığı varsayılmaz.

## Kurulum
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
- Repository: `ebabekirsahin/TKGM`
- Branch: `main`
- Main file: `app.py`

## Excel şeması
Zorunlu sütunlar: `İL`, `İlçe`, `Mahalle`, `ADA-PAFTA`, `PARSEL`.

TKGM koordinat sorgusunu kullanmak için isteğe bağlı sütunlar: `ENLEM`, `BOYLAM`. Koordinatlar WGS84 ondalık derece olmalıdır.

## Eşleştirme ve doğruluk
- Türkçe karakterler ve boşluk/noktalama normalize edilir.
- İl, ilçe, mahalle, ada/pafta ve parsel kimlikleri karşılaştırılır.
- Birden fazla eşleşme varsa kayıt doğrulama bekler.
- Kaynakta gerekli öznitelikler yoksa eşleşme kesin sayılmaz.
- Polygon/MultiPolygon geometrilerinden temsilî nokta ve alan hesaplanır.
- Uygulama resmî kadastro belgesi veya mülkiyet doğrulaması değildir.

## Gizlilik
Excel dosyaları uygulama oturumunda işlenir; kalıcı veri tabanı/depolama yapılandırılmadı. Yalnızca indirme/kullanım şartlarına uygun açık veri kaynaklarını kullanın.
