import io
import pandas as pd

def make_excel(results):
    output=io.BytesIO()
    with pd.ExcelWriter(output,engine="openpyxl") as writer:
        results.to_excel(writer,index=False,sheet_name="Taşınmaz Sonuçları")
        summary=results["Durum"].value_counts().rename_axis("Durum").reset_index(name="Adet")
        summary.to_excel(writer,index=False,sheet_name="Özet")
    output.seek(0)
    return output.getvalue()
