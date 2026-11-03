# Türkiye Taşınmaz Haritası

Streamlit uygulaması; Excel'deki il, ilçe, mahalle, ada/pafta ve parsel kayıtlarını gerçek geometri kaynaklarıyla eşleştirir. Gerçek parsel geometrisi bulunmadan haritada tahmini nokta veya sınır oluşturmaz.

## TKGM herkese açık koordinat sorgusu

Uygulama, TKGM Parsel Sorgu web istemcisinin herkese açık koordinat-temelli sorgusunu `sources/tkgm_public.py` üzerinden çağırabilir.

**Önemli sınır:** Bu uç nokta koordinat → parsel sorgusudur. İl/ilçe/mahalle/ada/parsel metninden koordinat üretmez ve Türkiye çapında toplu ada-parsel sorgusu için resmî, sınırsız bir API değildir. Excel'e isteğe bağlı `ENLEM` ve `BOYLAM` sütunları (WGS84/EPSG:4326) eklendiğinde uygulama koordinatları sorgular; dönen idari/parsel kimlikleri Excel satırıyla eşleşmeden geometriyi kabul etmez. Mahalle merkezi veya yaklaşık koordinat kullanılmaz.

Servis yanıtı 401/403 veya 429 verirse işlem durdurulur. Kimlik doğrulama, CAPTCHA veya erişim kısıtlamaları aşılmaya çalışılmaz. Uç nokta resmî bir toplu veri API'si değil, kamuya açık web istemcisinin sorgu akışıdır; TKGM kullanım şartları ve servis politikaları geçerlidir.

## Doğrudan entegre edilen açık parsel servisleri
- Kastamonu İl Özel İdaresi TKGM_PUBLIC / Parseller katmanı. Kaynakta ada ve parsel alanları var; ancak ilçe/mahalle doğrulaması sağlanmayan kayıtlar kesin eşleşme kabul edilmez.
- Pursaklar Belediyesi REHBER/mulkiyet / PARSEL katmanı. İlçe, mahalle, ada ve parsel alanlarını içerir; Excel satırlarıyla bu alanlar üzerinden sorgulanır.

Bu servisler yalnızca kapsadıkları yerlerde işe yarar. Kaynakların açık olması, tüm Türkiye parsellerini kapsadıkları anlamına gelmez.

## Otomatik açık veri keşfi
Uygulama ayrıca ArcGIS Online'ın herkese açık içerik kataloğunda parsel/kadastro Feature Service katmanlarını arar. Kimlik doğrulamasız katmanların alan şeması incelenir; il, ilçe, mahalle ve ada/parsel kimliklerini birlikte sunmayan katmanlar otomatik eşleştirmeye alınmaz. Katman başına kayıt sayısı sınırlandırılır. Yalnızca WGS84 (EPSG:4326) geometriler kabul edilir. Otomatik katalog araması, Türkiye'deki tüm belediye veya kadastro servislerini keşfettiği anlamına gelmez.

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

## Beş il için TKGM ada/parsel sorgusu

Manisa, Afyonkarahisar, Çanakkale, Malatya ve Adana kayıtlarında uygulama; il, ilçe ve mahalle kodlarını TKGM'nin herkese açık Parsel Sorgu/CBS idari listelerinden çözmeyi, ardından mahalle kodu + ada + parsel ile GeoJSON geometri istemeyi dener. Kod: `sources/tkgm_cadastral.py`. Kullanıcı onayı gerekir; HTTP 401/403/429 yanıtında sorgular durdurulur. Bu entegrasyon kamuya açık web istemcisiyle aynı API akışını kullanan bir istemci uygulamasıdır, hizmet garantili resmî toplu veri API'si olarak sunulmaz. 10.000 kayıt için süre ve kota servis yanıtlarına bağlıdır; önce küçük örnekle test edin.

### Adana / Seyhan açık belediye parsel katmanı

Seyhan Belediyesi KENTREHBERI ArcGIS REST hizmetinde `PARSEL` katmanı (MapServer/4) poligon geometri sunar. Alan şemasında `ADANO`, `PARSELNO` ve `MAHALLEID` alanları vardır. `MAHALLE` (MapServer/7) ve `İLÇE` (MapServer/6) katmanlarıyla GUID bağlantısı kurulur. Uygulama yalnızca kadastro türünü (`TIP=2`) sorgular. Kaynak: https://gispya.seyhan.bel.tr/arcgis/rest/services/KENTREHBERI/MapServer

Bu kaynak yalnızca Adana / Seyhan için geçerlidir; Adana'nın diğer ilçelerine genellenmez.
