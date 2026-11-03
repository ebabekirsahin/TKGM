"""Small, read-only smoke check for the five TKGM administrative list endpoints.

This checks connectivity and response parsing only. It deliberately does not issue
parcel requests or retrieve property geometries.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources.tkgm_cadastral import TKGMClient


def main():
    client = TKGMClient()
    problems = []
    for province_name in ("Manisa", "Afyonkarahisar", "Çanakkale", "Malatya", "Adana"):
        try:
            province = client.province(province_name)
            districts = client.admin_list("ilce", province["id"])
            if not districts:
                raise RuntimeError("İlçe listesi boş veya beklenmeyen JSON şeması döndü.")
            print(f"OK | {province_name} | id={province['id']} | {len(districts)} ilçe")
        except Exception as exc:
            problems.append((province_name, str(exc)))
            print(f"FAIL | {province_name} | {exc}")
    if problems:
        raise SystemExit(f"{len(problems)} il için canlı TKGM idari liste kontrolü başarısız.")

    # Verify the public Seyhan parcel and administrative join-layer schemas.
    import requests
    base = "https://gispya.seyhan.bel.tr/arcgis/rest/services/KENTREHBERI/MapServer"
    expected = {
        4: {"ADANO", "PARSELNO", "MAHALLEID", "TIP"},
        7: {"ID", "AD", "ILCEID"},
        6: {"ID", "AD"},
    }
    for layer_id, required_fields in expected.items():
        response = requests.get(f"{base}/{layer_id}", params={"f": "json"}, timeout=20)
        response.raise_for_status()
        metadata = response.json()
        if metadata.get("error"):
            raise RuntimeError(f"Seyhan layer {layer_id}: {metadata['error']}")
        fields = {field.get("name") for field in metadata.get("fields", [])}
        missing = required_fields - fields
        if missing:
            raise RuntimeError(f"Seyhan layer {layer_id} missing fields: {sorted(missing)}")
        if "Query" not in str(metadata.get("capabilities", "Query")):
            raise RuntimeError(f"Seyhan layer {layer_id} does not expose Query capability")
        print(f"OK | Seyhan layer {layer_id} | {metadata.get('name')} | schema valid")

    print("Tüm beş ilin idari liste uç noktaları erişilebilir.")


if __name__ == "__main__":
    main()
