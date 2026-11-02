from core.normalize import norm

def test_turkish_normalization():
    assert norm("İstanbul") == norm("istanbul")
    assert norm("Çankaya") == norm("cankaya")
