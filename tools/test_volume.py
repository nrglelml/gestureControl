"""
Ses kontrolü teşhis scripti
Çalıştır: python test_volume.py
"""

print("=" * 50)
print("  SES KONTROLÜ TEŞHİS")
print("=" * 50)

# 1. pycaw import testi
print("\n[1] pycaw import ediliyor...")
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    print("    OK — pycaw bulundu")
except ImportError as e:
    print(f"    HATA: {e}")
    print("    Çözüm: pip install pycaw comtypes")
    exit(1)

# 2. Ses cihazı testi
print("\n[2] Ses cihazları listeleniyor...")
try:
    sessions = AudioUtilities.GetAllSessions()
    for s in sessions:
        print(f"    Oturum: {s.Process and s.Process.name()}")
    
    devices = AudioUtilities.GetSpeakers()
    print(f"    Hoparlör cihazı: {devices}")
except Exception as e:
    print(f"    HATA: {e}")

# 3. Volume interface testi
print("\n[3] Volume interface başlatılıyor...")
try:
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    print("    OK — interface açıldı")
    
    current = volume.GetMasterVolumeLevelScalar()
    print(f"    Mevcut ses seviyesi: {int(current * 100)}%")
    
    muted = volume.GetMute()
    print(f"    Mute durumu: {'Sessiz' if muted else 'Açık'}")
except Exception as e:
    print(f"    HATA: {e}")
    print("    Bu hata genellikle yönetici yetkisi veya cihaz sorunundan kaynaklanır")
    exit(1)

# 4. Ses değiştirme testi
print("\n[4] Ses değiştirme testi...")
try:
    original = volume.GetMasterVolumeLevelScalar()
    print(f"    Mevcut: {int(original*100)}%")
    
    test_val = max(0.0, min(1.0, original + 0.05))
    volume.SetMasterVolumeLevelScalar(test_val, None)
    after = volume.GetMasterVolumeLevelScalar()
    print(f"    +5% sonrası: {int(after*100)}%")
    
    # Geri al
    volume.SetMasterVolumeLevelScalar(original, None)
    restored = volume.GetMasterVolumeLevelScalar()
    print(f"    Geri alındı: {int(restored*100)}%")
    
    if abs(after - test_val) < 0.02:
        print("    SONUÇ: Ses kontrolü ÇALIŞIYOR ✓")
    else:
        print("    SONUÇ: Değer değişmedi — cihaz sorunu olabilir")

except Exception as e:
    print(f"    HATA: {e}")

# 5. Alternatif yöntem: pyautogui tuş basımı
print("\n[5] pyautogui ses tuşları testi...")
try:
    import pyautogui
    print("    pyautogui bulundu")
    print("    3 saniye içinde ses tuşu basılacak (volumeup)...")
    import time
    time.sleep(3)
    pyautogui.press('volumeup')
    print("    volumeup tuşu gönderildi — ses değişti mi?")
except ImportError:
    print("    pyautogui bulunamadı: pip install pyautogui")
except Exception as e:
    print(f"    HATA: {e}")

print("\n" + "=" * 50)
print("  Teşhis tamamlandı")
print("=" * 50)
