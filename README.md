# 🖐 Gesture Control — Windows

Webcam ve el hareketleriyle bilgisayarı kontrol et. Ekrana dokunmadan ses ayarla, müzik değiştir, sekme geç, uygulama kapat.

> **Geliştirme durumu:** Aktif geliştirme aşamasında. Tablet (Android) versiyonu yapım aşamasında.

---

## Gereksinimler

### İşletim Sistemi
- **Windows 10 veya Windows 11** (zorunlu — ses kontrolü Windows API'sine bağlı)
- macOS / Linux desteklenmiyor

### Python
- **Python 3.9 – 3.11** önerilir
- Python 3.12+ bazı MediaPipe sürümleriyle uyumsuzluk yaşayabilir
- İndirmek için: https://www.python.org/downloads/

Python sürümünü kontrol et:
```bash
python --version
```

### Webcam
- Dahili veya harici herhangi bir webcam çalışır
- Minimum 480p çözünürlük önerilir
- Birden fazla kamera varsa `CAMERA_INDEX` ayarını değiştir (bkz. [Ayarlar](#ayarlar))

### Kütüphaneler
Aşağıdaki Python kütüphaneleri gereklidir:

| Kütüphane | Sürüm | Açıklama |
|-----------|-------|----------|
| mediapipe | ≥ 0.10.0 | El tespiti ve landmark modeli |
| opencv-python | ≥ 4.8.0 | Kamera erişimi ve görüntü işleme |
| numpy | ≥ 1.24.0 | Sayısal hesaplamalar |
| pyautogui | ≥ 0.9.54 | Klavye/medya tuşu simülasyonu |
| pycaw | ≥ 20230407 | Windows ses API'si (hassas % kontrolü) |
| comtypes | ≥ 1.2.0 | Windows COM nesneleri (pycaw için) |

---

## Kurulum

### 1. Repoyu klonla
```bash
git clone https://github.com/kullanici-adi/gesture-control.git
cd gesture-control
```

### 2. (Önerilir) Sanal ortam oluştur
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# PowerShell:
venv\Scripts\Activate.ps1
```

### 3. Kütüphaneleri yükle
```bash
pip install -r requirements.txt
```

Yükleme başarılıysa şöyle görünmeli:
```
Successfully installed mediapipe-0.10.x opencv-python-4.x.x ...
```

### 4. Çalıştır
```bash
python gesture_control.py
```

---

## Kullanım

Uygulama açılınca kamera görüntüsü penceresi açılır. Elinizi kameraya tutun.

### Temel kurallar
- Hareketi **0.9 saniye** sabit tut → komut tetiklenir
- Sol alttaki yeşil bar dolunca komut çalışır
- Komutlar arası **1.3 saniyelik** bekleme var (yanlışlıkla tetiklenmeyi önler)
- Elin kameraya olan mesafesi önemli — çok uzakta olunca ekranda kırmızı daire ve "Yaklaş" uyarısı çıkar

### Tuşlar
| Tuş | Eylem |
|-----|-------|
| `Q` | Uygulamadan çık |
| `L` | Landmark (iskelet) çizimini aç/kapat |

---

## El Hareketi Komutları

### Sol El

| Parmak Sayısı | Komut |
|---------------|-------|
| ☝ 1 parmak | Ses artır (+%10) |
| ✌ 2 parmak | Ses azalt (-%10) |
| 3 parmak | Oynat / Durdur |
| 4 parmak | Sonraki parça |
| 5 parmak + sağa kaydır | Sonraki parça |
| 5 parmak + sola kaydır | Önceki parça |

### Sağ El

| Parmak Sayısı | Komut |
|---------------|-------|
| ☝ 1 parmak | Sonraki sekme (Ctrl+Tab) |
| ✌ 2 parmak | Önceki sekme (Ctrl+Shift+Tab) |
| 3 parmak | Uygulama değiştir (Alt+Tab) |
| 3 parmak × N kez | N uygulama ileri atla |
| 4 parmak | Sessiz / Sesi aç (Mute toggle) |
| 5 parmak | Pencere kapat (onay gerekir) |

### Pencere Kapatma Onayı
Sağ el 5 parmak tutulunca bir onay kutusu açılır:
- **TAMAM** butonuna bas → aktif pencere kapanır
- **El ile OK işareti yap** (baş parmak + işaret parmağı ucu birleşik, diğerleri açık) → kapanır
- **İptal** veya elinizi çekin → iptal olur

---

## Ayarlar

`gesture_control.py` dosyasının üstündeki sabitler değiştirilebilir:

```python
HOLD_TIME        = 0.9    # Komut tetikleme süresi (saniye) — düşürürsen daha hızlı
COOLDOWN         = 1.3    # Komutlar arası minimum bekleme (saniye)
CAMERA_INDEX     = 0      # Webcam numarası — birden fazla kamera varsa 1, 2 dene
FLIP_CAMERA      = True   # True = ayna görüntüsü (selfie modu)
SHOW_LANDMARKS   = True   # El iskelet noktalarını göster/gizle
VOLUME_STEP      = 0.10   # Ses adım büyüklüğü (0.10 = %10)
MIN_HAND_AREA    = 0.010  # Minimum el alanı — yükseltirsen uzak eller yok sayılır
MIN_CONFIDENCE   = 0.75   # MediaPipe tespit güveni — yükseltirsen daha seçici
THUMB_OPEN_RATIO = 0.32   # Baş parmak açık/kapalı eşiği — kendi eline göre ayarla
```

### Baş parmak eşiğini ayarlamak
Parmak sayısı 1 fazla veya 1 eksik geliyorsa `THUMB_OPEN_RATIO` değerini değiştir:
- Çok fazla geliyorsa → değeri **artır** (örn. 0.40)
- Çok az geliyorsa → değeri **düşür** (örn. 0.25)

Tam değeri bulmak için `tools/debug_thumb.py` scriptini kullan (bkz. [Geliştirici Araçları](#geliştirici-araçları)).

---

## Ses Kontrolü Hakkında

Uygulama önce **pycaw** (Windows Core Audio API) ile hassas % kontrolü yapmayı dener. Başarısız olursa otomatik olarak **pyautogui** klavye tuşlarına (volumeup/volumedown) düşer.

Başlatırken terminalde şunu görmeli:
```
[+] Ses: pycaw (mevcut: 45%)   ← hassas mod, ideal
```
veya:
```
[+] Ses: pyautogui             ← tuş modu, çalışır ama % göstergesi tahmini
```

---

## Geliştirici Araçları

`tools/` klasöründe tanı ve test scriptleri bulunur:

### `tools/debug_thumb.py`
Baş parmak tespitini canlı görselleştirir. Alttaki bar ve ratio değeri ile `THUMB_OPEN_RATIO` eşiğini kendi eline göre ayarlayabilirsin.
```bash
python tools/debug_thumb.py
```

### `tools/debug_fingers.py`
Her parmağın açık/kapalı durumunu ve toplam sayımı canlı gösterir.
```bash
python tools/debug_fingers.py
```

### `tools/test_volume.py`
pycaw ses kontrolünü adım adım test eder. Ses komutu çalışmıyorsa önce bunu çalıştır.
```bash
python tools/test_volume.py
```

---

## Sorun Giderme

### Webcam açılmıyor
```python
# gesture_control.py içinde:
CAMERA_INDEX = 1  # veya 2, 3 dene
```

### "El bulunamadı" sürekli çıkıyor
- Işığı artır — MediaPipe karanlıkta zorlanır
- Elinizi kameraya daha yakın tut (ekranın en az %1'ini kaplasın)
- `MIN_CONFIDENCE = 0.65` yaparak eşiği düşür

### Parmak sayısı hatalı
1. `python tools/debug_thumb.py` çalıştır
2. Baş parmak açık/kapalı ratio değerlerine bak
3. `THUMB_OPEN_RATIO` değerini README'deki [Ayarlar](#ayarlar) bölümüne göre düzelt

### Ses çalışmıyor
```bash
python tools/test_volume.py
```
Hata mesajına göre:
- `'AudioDevice' object has no attribute 'Activate'` → pycaw sürüm sorunu, uygulama otomatik pyautogui'ye geçer, ses yine çalışır
- `Access denied` → Python'u yönetici olarak çalıştır

### MediaPipe hatası / import error
```bash
pip install mediapipe --upgrade
pip install opencv-python --upgrade
```

### pyautogui medya tuşları çalışmıyor
Bazı sistemlerde medya tuşları (nexttrack, prevtrack) çalışmayabilir. Spotify, Windows Media Player gibi uygulamaların odakta olması gerekebilir.

---

## Proje Yapısı

```
gesture-control/
├── gesture_control.py      ← Ana uygulama
├── requirements.txt        ← Python bağımlılıkları
├── README.md
└── tools/                  ← Tanı ve test araçları
    ├── debug_thumb.py      ← Baş parmak eşiği ayarı
    ├── debug_fingers.py    ← Parmak sayımı görselleştirme
    └── test_volume.py      ← Ses kontrolü testi
```

---

## Teknik Detaylar

- **El tespiti:** MediaPipe Hands (Google) — 21 landmark, gerçek zamanlı
- **Parmak sayımı:** TIP.y < PIP.y yöntemi (4 parmak) + mesafe tabanlı baş parmak tespiti
- **Stabilizasyon:** Son 6 frame'in majority vote'u — anlık titremeler komutu tetiklemez
- **Swipe algılama:** Bileğin x ekseni geçmişi deque ile takip edilir
- **Ses kontrolü:** Windows IMMDeviceEnumerator → IAudioEndpointVolume (COM API)

---

## Lisans

MIT License — serbestçe kullanabilir, değiştirebilir, dağıtabilirsin.