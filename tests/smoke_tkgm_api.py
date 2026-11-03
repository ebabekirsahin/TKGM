"""Small, read-only smoke check for the five TKGM administrative list endpoints.

This checks connectivity and response parsing only. It deliberately does not issue
parcel requests or retrieve property geometries.
"""
from sources.tkgm_cadastral import IL_IDS, TKGMClient


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
    print("Tüm beş ilin idari liste uç noktaları erişilebilir.")


if __name__ == "__main__":
    main()
