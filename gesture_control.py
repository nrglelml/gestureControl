"""
Gesture Control - Windows  v4.0
Araştırma bulgularına göre yeniden yazıldı:
- Baş parmak: uç(4)-IP(3) mesafesi / el genişliği (yön bağımsız)
- Diğer parmaklar: TIP.y < PIP.y (MediaPipe standardı, flip sonrası güvenilir)
- Parmak stabilizasyonu: 6 frame majority vote
- Onay: hem mesaj kutusu hem OK işareti, Alt+F4 sonra kutu kapanır
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import threading
from collections import deque, Counter

import tkinter as tk
from tkinter import messagebox

try:
    import comtypes.client
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    try:
        from pycaw.pycaw import IMMDeviceEnumerator
    except ImportError:
        IMMDeviceEnumerator = None
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Renkler (BGR)
C_BG     = (20,  20,  20)
C_TEAL   = (160, 180, 50)
C_PURPLE = (200, 100, 180)
C_WHITE  = (240, 240, 240)
C_GRAY   = (120, 120, 120)
C_GREEN  = (80,  200, 80)
C_RED    = (80,  80,  220)
C_AMBER  = (50,  180, 230)
C_ORANGE = (30,  140, 255)

# Ayarlar
HOLD_TIME        = 0.9
COOLDOWN         = 1.3
CAMERA_INDEX     = 0
FLIP_CAMERA      = True
SHOW_LANDMARKS   = True
VOLUME_STEP      = 0.10
MIN_HAND_AREA    = 0.010   # Biraz düşürdük — el biraz uzakta olunca da çalışsın
MIN_CONFIDENCE   = 0.75
SWIPE_MIN_DIST   = 0.11
SWIPE_HISTORY    = 0.9
SWIPE_COOLDOWN   = 0.8
SWIPE_FINGER_MIN = 4
VOTE_FRAMES      = 6       # Stabilizasyon için frame sayısı

# Baş parmak eşiği: uç(4) ile IP(3) arası mesafe / el genişliği
# Araştırmaya göre: 0.30–0.40 arası optimal
THUMB_OPEN_RATIO = 0.32


class VolumeController:
    def __init__(self):
        self.volume     = None
        self._sim_level = 0.5
        self._muted     = False
        self.mode       = "none"
        if PYCAW_AVAILABLE:
            try:
                self.volume = self._open_endpoint()
                lvl = self.volume.GetMasterVolumeLevelScalar()
                self._sim_level = lvl
                self.mode = "pycaw"
                print(f"[+] Ses: pycaw ({int(lvl*100)}%)")
            except Exception as e:
                print(f"[!] pycaw: {e}")
        if self.mode == "none" and PYAUTOGUI_AVAILABLE:
            self.mode = "keys"
            print("[+] Ses: pyautogui")
        if self.mode == "none":
            print("[!] Ses devre disi")

    def _open_endpoint(self):
        from comtypes import GUID
        CLSID = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
        obj = comtypes.client.CreateObject(CLSID, interface=comtypes.IUnknown, clsctx=CLSCTX_ALL)
        imm = IMMDeviceEnumerator if IMMDeviceEnumerator else \
              __import__('pycaw.pycaw', fromlist=['IMMDeviceEnumerator']).IMMDeviceEnumerator
        dev = obj.QueryInterface(imm).GetDefaultAudioEndpoint(0, 0)
        return cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
                    POINTER(IAudioEndpointVolume))

    def get_level(self):
        if self.mode == "pycaw":
            try: return self.volume.GetMasterVolumeLevelScalar()
            except: pass
        return self._sim_level

    def change(self, delta):
        new = max(0.0, min(1.0, self.get_level() + delta))
        if self.mode == "pycaw":
            try:
                self.volume.SetMasterVolumeLevelScalar(new, None)
                self._sim_level = new
                return new
            except: self.mode = "keys"
        if self.mode == "keys" and PYAUTOGUI_AVAILABLE:
            for _ in range(max(1, round(abs(delta)/0.02))):
                pyautogui.press('volumeup' if delta > 0 else 'volumedown')
            self._sim_level = new
        return self._sim_level

    def toggle_mute(self):
        if self.mode == "pycaw":
            try:
                m = self.volume.GetMute()
                self.volume.SetMute(not m, None)
                return not m
            except: pass
        if PYAUTOGUI_AVAILABLE: pyautogui.press('volumemute')
        self._muted = not self._muted
        return self._muted

    def is_muted(self):
        if self.mode == "pycaw":
            try: return bool(self.volume.GetMute())
            except: pass
        return self._muted


class CommandExecutor:
    def __init__(self, vol):
        self.vol = vol
        self.last_feedback = ""
        self.feedback_time = 0

    def execute(self, command, repeat=1):
        fb = ""
        if command == "vol_up":
            fb = f"Ses: {int(self.vol.change(VOLUME_STEP)*100)}%  +"
        elif command == "vol_down":
            fb = f"Ses: {int(self.vol.change(-VOLUME_STEP)*100)}%  -"
        elif command == "play_pause":
            if PYAUTOGUI_AVAILABLE: pyautogui.press('playpause')
            fb = "Oynat / Durdur"
        elif command == "next_track":
            if PYAUTOGUI_AVAILABLE: pyautogui.press('nexttrack')
            fb = "Sonraki parca >>"
        elif command == "prev_track":
            if PYAUTOGUI_AVAILABLE: pyautogui.press('prevtrack')
            fb = "<< Onceki parca"
        elif command == "next_tab":
            if PYAUTOGUI_AVAILABLE: pyautogui.hotkey('ctrl', 'tab')
            fb = "Sonraki sekme ->"
        elif command == "prev_tab":
            if PYAUTOGUI_AVAILABLE: pyautogui.hotkey('ctrl', 'shift', 'tab')
            fb = "<- Onceki sekme"
        elif command == "alt_tab":
            if PYAUTOGUI_AVAILABLE:
                pyautogui.keyDown('alt')
                for _ in range(repeat):
                    pyautogui.press('tab')
                    time.sleep(0.12)
                pyautogui.keyUp('alt')
            fb = f"Uygulama degistir (x{repeat})"
        elif command == "mute":
            fb = "SESSIZ" if self.vol.toggle_mute() else "Ses acildi"
        elif command == "close_window":
            if PYAUTOGUI_AVAILABLE:
                time.sleep(0.05)   # Kutunun tam kapanmasını bekle
                pyautogui.hotkey('alt', 'f4')
            fb = "Pencere kapatildi"
        if fb:
            self.last_feedback = fb
            self.feedback_time = time.time()

    def get_feedback(self):
        return self.last_feedback if time.time() - self.feedback_time < 2.5 else ""


class GestureDetector:
    """
    Parmak sayımı — araştırma bulgularına göre:

    BAŞTPARMAK: uç(4) ile IP eklemi(3) arası mesafe / el genişliği.
    El yönünden (avuç/sırt) ve sağ/sol farkından bağımsız çalışır.
    Kaynak: github.com/d-kleine/finger_counter_webcam

    DİĞER 4 PARMAK: TIP.y < PIP.y — parmak yukarıdaysa açık.
    MediaPipe'in resmi dokümantasyonundaki standart yöntem.
    Kaynak: mediapipe.readthedocs.io/en/latest/solutions/hands.html

    STABİLİZASYON: Son VOTE_FRAMES frame'in majority vote'u kullanılır.
    """

    # PIP (Proximal Inter-Phalangeal) landmark ID'leri
    # TIP:  8, 12, 16, 20
    # PIP:  6, 10, 14, 18
    FINGER_TIPS = [8,  12, 16, 20]
    FINGER_PIPS = [6,  10, 14, 18]

    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=MIN_CONFIDENCE,
            min_tracking_confidence=0.70,
            model_complexity=1)
        self.mp_draw = mp.solutions.drawing_utils
        self._buf = {"Left": deque(maxlen=VOTE_FRAMES),
                     "Right": deque(maxlen=VOTE_FRAMES)}

    def _raw_count(self, lm):
        """
        Ham parmak sayımı — stabilizasyonsuz.
        lm: landmarks.landmark listesi
        """
        # Baş parmak: uç(4) ile işaret MCP(5) arası mesafe / el genişliği
        # Açıkken uzak, kapalıyken yakın — en belirgin farkı veren referans
        tip  = np.array([lm[4].x, lm[4].y])
        mcp5 = np.array([lm[5].x, lm[5].y])   # İşaret parmağı kökü
        w    = np.array([lm[0].x, lm[0].y])
        p17  = np.array([lm[17].x, lm[17].y])
        hw   = np.linalg.norm(w - p17) + 1e-6
        count = 1 if np.linalg.norm(tip - mcp5) / hw > THUMB_OPEN_RATIO else 0

        # Diğer 4 parmak: TIP.y < PIP.y
        for tip_id, pip_id in zip(self.FINGER_TIPS, self.FINGER_PIPS):
            if lm[tip_id].y < lm[pip_id].y:
                count += 1
        return count

    def count_fingers(self, landmarks, handedness):
        """Majority vote ile stabilize sayım."""
        raw = self._raw_count(landmarks.landmark)
        buf = self._buf[handedness]
        buf.append(raw)
        if len(buf) < 3:
            return raw
        return Counter(buf).most_common(1)[0][0]

    def is_ok_sign(self, landmarks):
        """
        OK işareti: baş parmak ucu (4) ile işaret ucu (8) yakın
        VE orta/yüzük/serçe açık.
        Eşik geniş tutuldu (0.12) — parmak tam birleşmese de çalışsın.
        """
        lm = landmarks.landmark
        d  = np.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
        if d > 0.12:
            return False
        # Orta, yüzük, serçe açık (TIP.y < PIP.y)
        return all(lm[t].y < lm[t-2].y for t in [12, 16, 20])

    def hand_area_ratio(self, landmarks):
        xs = [l.x for l in landmarks.landmark]
        ys = [l.y for l in landmarks.landmark]
        return (max(xs)-min(xs)) * (max(ys)-min(ys))

    def wrist_x(self, landmarks):
        return landmarks.landmark[0].x

    def get_static_gesture(self, landmarks, handedness):
        count = self.count_fingers(landmarks, handedness)
        if handedness == "Left":
            # 5 parmak → swipe (ana döngüde)
            return {1:"vol_up", 2:"vol_down", 3:"play_pause", 4:"next_track"}.get(count)
        else:
            return {1:"next_tab", 2:"prev_tab", 3:"alt_tab",
                    4:"mute", 5:"close_confirm"}.get(count)

    def process(self, frame_rgb):
        return self.hands.process(frame_rgb)

    def draw_landmarks(self, frame, lm, handedness):
        color = C_TEAL if handedness == "Left" else C_PURPLE
        self.mp_draw.draw_landmarks(
            frame, lm, self.mp_hands.HAND_CONNECTIONS,
            self.mp_draw.DrawingSpec(color=color, thickness=2, circle_radius=4),
            self.mp_draw.DrawingSpec(color=C_WHITE, thickness=1))


class SwipeTracker:
    def __init__(self):
        self.history    = deque()
        self.last_fire  = 0.0
        self.last_count = 0

    def reset(self):
        self.history.clear()
        self.last_count = 0

    def update(self, finger_count, wrist_x, now):
        if finger_count != self.last_count:
            self.history.clear()
        self.last_count = finger_count

        if finger_count < SWIPE_FINGER_MIN:
            self.history.clear()
            return None

        self.history.append((now, wrist_x))
        while self.history and (now - self.history[0][0]) > SWIPE_HISTORY:
            self.history.popleft()

        if len(self.history) < 4:
            return None
        if (now - self.last_fire) < SWIPE_COOLDOWN:
            return None

        delta = wrist_x - self.history[0][1]
        if abs(delta) >= SWIPE_MIN_DIST:
            cmd = "prev_track" if delta < 0 else "next_track"
            self.last_fire = now
            self.history.clear()
            return cmd
        return None


class ConfirmDialog:
    """
    Tkinter onay kutusu ayrı thread'de açılır.
    TAMAM → on_confirm()  (Alt+F4 gönderir, kutu kapanır)
    İptal → on_cancel()
    OK işareti → aynı on_confirm() çağrılır
    """
    def __init__(self, on_confirm, on_cancel):
        self._on_confirm = on_confirm
        self._on_cancel  = on_cancel
        self._root       = None
        self._done       = False
        self._thread = threading.Thread(target=self._show, daemon=True)
        self._thread.start()

    def _show(self):
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.attributes('-topmost', True)
        self._root.lift()
        self._root.focus_force()
        result = messagebox.askokcancel(
            "Pencereyi Kapat",
            "Aktif pencere kapatilacak!\n\n"
            "  TAMAM  → Pencereyi kapat\n"
            "  Iptal  → Vazgec\n\n"
            "Ya da el ile OK (👌🏻) isareti yapin.",
            parent=self._root
        )
        if not self._done:
            self._done = True
            self._root.destroy()
            self._root = None
            if result:
                self._on_confirm()
            else:
                self._on_cancel()

    def confirm_from_gesture(self):
        """
        OK işareti geldiğinde çağrılır.
        Sira önemli:
        1. Alt+F4 gönder (o an aktif pencere = asıl uygulama, kutu henüz açık)
        2. Kısa bekle
        3. Tkinter kutusunu kapat
        """
        if self._done:
            return
        self._done = True

        def _close():
            # Adım 1: Alt+F4 — kutu henüz aktif değil, asıl pencere hedef
            if PYAUTOGUI_AVAILABLE:
                import pyautogui as _pag
                _pag.hotkey('alt', 'f4')
            import time as _t
            _t.sleep(0.15)
            # Adım 2: Tkinter kutusunu kapat
            if self._root:
                try:
                    self._root.after(0, self._root.destroy)
                except Exception:
                    pass
            self._root = None
            # Adım 3: Executor feedback
            self._on_confirm()

        threading.Thread(target=_close, daemon=True).start()


class HUD:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.f  = cv2.FONT_HERSHEY_SIMPLEX
        self.fb = cv2.FONT_HERSHEY_DUPLEX

    def _panel(self, img, x1, y1, x2, y2, alpha=0.62):
        ov = img.copy()
        cv2.rectangle(ov, (x1,y1), (x2,y2), C_BG, -1)
        cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)
        cv2.rectangle(img, (x1,y1), (x2,y2), C_GRAY, 1)

    def _bar(self, img, x, y, w, h, val, color):
        cv2.rectangle(img,(x,y),(x+w,y+h),C_GRAY,-1)
        cv2.rectangle(img,(x,y),(x+int(w*val),y+h),color,-1)

    def render(self, frame, state):
        W, H = self.w, self.h
        # Sol panel
        self._panel(frame, 8, 8, 272, 175)
        cv2.putText(frame,"GESTURE CONTROL v4",(18,32),self.fb,0.46,C_TEAL,1,cv2.LINE_AA)
        labels = state.get("hand_labels",[])
        cv2.putText(frame," | ".join(labels) or "El bulunamadi",
                    (18,56),self.f,0.42,C_WHITE,1,cv2.LINE_AA)
        gmap = {
            "vol_up":"1p Sol - Ses +","vol_down":"2p Sol - Ses -",
            "play_pause":"3p Sol - Oynat/Dur",
            "next_track":"Sol 4p - Sonraki / saga kaydir",
            "prev_track":"Sol 5p - sola kaydir",
            "next_tab":"1p Sag - Sonraki sekme",
            "prev_tab":"2p Sag - Onceki sekme",
            "alt_tab":"3p Sag - Uygulama degistir",
            "mute":"4p Sag - Mute",
            "close_confirm":"5p Sag - Onay bekleniyor...",
        }
        raw = state.get("active_gesture","")
        cv2.putText(frame, gmap.get(raw, raw or "—"),
                    (18,78),self.f,0.36,C_AMBER,1,cv2.LINE_AA)
        prog = state.get("hold_progress",0.0)
        self._bar(frame,18,90,244,6,prog,
                  C_GRAY if state.get("cooldown_active") else C_GREEN)
        cv2.putText(frame,"Bekleniyor..." if prog<1.0 else "Tetiklendi!",
                    (18,110),self.f,0.35,C_GRAY,1,cv2.LINE_AA)
        vol,muted = state.get("volume_level",0.5), state.get("muted",False)
        cv2.putText(frame,"SESSIZ" if muted else f"Ses: {int(vol*100)}%",
                    (18,135),self.f,0.42,C_RED if muted else C_WHITE,1,cv2.LINE_AA)
        if not muted: self._bar(frame,18,143,244,4,vol,C_AMBER)
        area = state.get("hand_area",0.0)
        cv2.putText(frame,f"Alan:{area:.3f} (min {MIN_HAND_AREA})",
                    (18,168),self.f,0.30,
                    C_GREEN if area>=MIN_HAND_AREA else C_RED,1,cv2.LINE_AA)

        # Onay banner
        if state.get("confirm_mode"):
            ov = frame.copy()
            cv2.rectangle(ov,(W//2-250,H//2-55),(W//2+250,H//2+55),(20,20,60),-1)
            cv2.addWeighted(ov,0.82,frame,0.18,0,frame)
            cv2.rectangle(frame,(W//2-250,H//2-55),(W//2+250,H//2+55),C_PURPLE,2)
            cv2.putText(frame,"Pencere kapatilacak!",
                        (W//2-185,H//2-18),self.fb,0.65,C_WHITE,1,cv2.LINE_AA)
            cv2.putText(frame,"OK isareti = onayla  |  TAMAM butonu = onayla",
                        (W//2-210,H//2+22),self.f,0.40,C_GREEN,1,cv2.LINE_AA)
            # OK mesafesi (debug)
            ok_dist = state.get("ok_dist", 0.0)
            bar_col = C_GREEN if ok_dist < 0.12 else C_GRAY
            self._bar(frame, W//2-200, H//2+42, 400, 6,
                      min(1.0, (0.12 - ok_dist + 0.12) / 0.24), bar_col)
            cv2.putText(frame, f"OK mesafe: {ok_dist:.3f} (esik <0.12)",
                        (W//2-100, H//2+60), self.f, 0.34, C_GRAY, 1)

        # Feedback
        fb = state.get("feedback","")
        if fb:
            tw = len(fb)*13
            fx = (W-tw)//2
            self._panel(frame,fx-12,H-90,fx+tw+12,H-55,0.75)
            cv2.putText(frame,fb,(fx,H-63),self.fb,0.62,C_GREEN,1,cv2.LINE_AA)

        # Sağ rehber
        self._panel(frame,W-235,8,W-8,240)
        cv2.putText(frame,"SOL EL",(W-225,30),self.fb,0.42,C_TEAL,1,cv2.LINE_AA)
        for i,t in enumerate(["1: Ses +","2: Ses -","3: Oynat/Dur",
                               "4: Sonraki parca",
                               "5+saga kaydir: Sonraki",
                               "5+sola kaydir: Onceki"]):
            cv2.putText(frame,t,(W-225,50+i*22),self.f,0.32,C_WHITE,1,cv2.LINE_AA)
        cv2.putText(frame,"SAG EL",(W-225,198),self.fb,0.42,C_PURPLE,1,cv2.LINE_AA)
        for i,t in enumerate(["1: Sonraki sekme","2: Onceki sekme",
                               "3: Uyg.degistir (tekrar=+atla)",
                               "4: Mute","5: Pencere kapat"]):
            cv2.putText(frame,t,(W-225,216+i*20),self.f,0.30,C_WHITE,1,cv2.LINE_AA)
        cv2.putText(frame,"Q:Cikis  L:Landmark",(8,H-10),self.f,0.36,C_GRAY,1,cv2.LINE_AA)


def main():
    print("\n"+"="*50)
    print("  GESTURE CONTROL  v4.0")
    print("="*50)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[HATA] Webcam acilamadi (index {CAMERA_INDEX})")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  Cozunurluk: {W}x{H}\n")

    vol_ctrl = VolumeController()
    executor = CommandExecutor(vol_ctrl)
    detector = GestureDetector()
    swiper   = SwipeTracker()
    hud      = HUD(W, H)

    gesture_start  = {}
    last_cmd_t     = 0.0
    show_lm        = SHOW_LANDMARKS
    confirm_mode   = False
    confirm_dialog = None   # ConfirmDialog nesnesi

    alt_tab_count  = 0
    alt_tab_last   = 0.0
    ALT_TAB_WINDOW = 2.0

    def on_confirm():
        nonlocal confirm_mode, confirm_dialog
        executor.execute("close_window")
        confirm_mode   = False
        confirm_dialog = None

    def on_cancel():
        nonlocal confirm_mode, confirm_dialog
        executor.last_feedback = "Iptal edildi"
        executor.feedback_time = time.time()
        confirm_mode   = False
        confirm_dialog = None

    print("  Hazir!  Q=cikis  L=landmark\n")

    while True:
        ret, frame = cap.read()
        if not ret: break
        if FLIP_CAMERA: frame = cv2.flip(frame, 1)

        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = detector.process(rgb)

        now             = time.time()
        cooldown_active = (now - last_cmd_t) < COOLDOWN
        hand_labels     = []
        dominant        = None
        hold_progress   = 0.0
        max_area        = 0.0
        ok_dist_display = 1.0

        if results.multi_hand_landmarks:
            for hand_lm, hand_info in zip(results.multi_hand_landmarks,
                                          results.multi_handedness):
                side = hand_info.classification[0].label
                conf = hand_info.classification[0].score
                if conf < MIN_CONFIDENCE:
                    continue

                area = detector.hand_area_ratio(hand_lm)
                max_area = max(max_area, area)

                if area < MIN_HAND_AREA:
                    if show_lm: detector.draw_landmarks(frame, hand_lm, side)
                    cx = int(np.mean([l.x for l in hand_lm.landmark])*W)
                    cy = int(np.mean([l.y for l in hand_lm.landmark])*H)
                    cv2.circle(frame,(cx,cy),20,C_RED,2)
                    cv2.putText(frame,"Yaklas",(cx-22,cy-24),
                                cv2.FONT_HERSHEY_SIMPLEX,0.38,C_RED,1)
                    continue

                hand_labels.append("Sol" if side=="Left" else "Sag")
                if show_lm: detector.draw_landmarks(frame, hand_lm, side)

                fc = detector.count_fingers(hand_lm, side)
                wx = detector.wrist_x(hand_lm)

                # OK mesafesini her zaman hesapla (onay modunda göster)
                lmpts = hand_lm.landmark
                ok_d  = np.hypot(lmpts[4].x-lmpts[8].x, lmpts[4].y-lmpts[8].y)
                ok_dist_display = min(ok_dist_display, ok_d)

                # ── ONAY MODU ─────────────────────────────────────────────────
                if confirm_mode:
                    if detector.is_ok_sign(hand_lm) and confirm_dialog:
                        confirm_dialog.confirm_from_gesture()
                    continue

                # ── SOL EL SWIPE (4-5 parmak) ─────────────────────────────────
                if side == "Left" and fc >= SWIPE_FINGER_MIN:
                    cmd = swiper.update(fc, wx, now)
                    if cmd and not cooldown_active:
                        executor.execute(cmd)
                        last_cmd_t = now
                        gesture_start = {}
                    dominant = "prev_track" if fc >= SWIPE_FINGER_MIN else "next_track"
                    cy2 = int(hand_lm.landmark[0].y * H)
                    cxw = int(wx * W)
                    cv2.arrowedLine(frame,(cxw-30,cy2),(cxw-65,cy2),C_TEAL,2,tipLength=0.45)
                    cv2.arrowedLine(frame,(cxw+30,cy2),(cxw+65,cy2),C_TEAL,2,tipLength=0.45)
                    continue
                elif side == "Left":
                    swiper.reset()

                # ── STATİK HAREKET ─────────────────────────────────────────────
                gesture = detector.get_static_gesture(hand_lm, side)
                if gesture:
                    key = f"{side}_{gesture}"
                    if key not in gesture_start:
                        gesture_start = {key: now}
                    elapsed  = now - gesture_start[key]
                    progress = min(elapsed / HOLD_TIME, 1.0)
                    if dominant is None:
                        dominant      = gesture
                        hold_progress = progress
                    if elapsed >= HOLD_TIME and not cooldown_active:
                        if gesture == "close_confirm" and not confirm_mode:
                            confirm_mode   = True
                            confirm_dialog = ConfirmDialog(on_confirm, on_cancel)
                            last_cmd_t     = now
                        elif gesture == "alt_tab":
                            if (now - alt_tab_last) < ALT_TAB_WINDOW:
                                alt_tab_count += 1
                            else:
                                alt_tab_count = 1
                            alt_tab_last = now
                            executor.execute("alt_tab", repeat=alt_tab_count)
                            last_cmd_t = now
                        else:
                            executor.execute(gesture)
                            last_cmd_t = now
                        gesture_start = {}
                else:
                    gesture_start = {}
        else:
            gesture_start = {}
            swiper.reset()
            if confirm_mode and confirm_dialog:
                confirm_mode   = False
                confirm_dialog = None

        state = {
            "active_gesture":  dominant,
            "hand_labels":     hand_labels,
            "hold_progress":   hold_progress,
            "cooldown_active": cooldown_active,
            "feedback":        executor.get_feedback(),
            "volume_level":    vol_ctrl.get_level(),
            "muted":           vol_ctrl.is_muted(),
            "confirm_mode":    confirm_mode,
            "ok_dist":         ok_dist_display,
            "hand_area":       max_area,
        }
        hud.render(frame, state)
        cv2.imshow("Gesture Control", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord('q'): break
        elif k == ord('l'): show_lm = not show_lm

    cap.release()
    cv2.destroyAllWindows()
    print("\n  Cikis yapildi.")

if __name__ == "__main__":
    main()