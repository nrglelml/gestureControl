"""
Parmak sayımı debug scripti v2
Çalıştır: python debug_fingers.py
"""

import cv2
import mediapipe as mp
import numpy as np

MIN_CONFIDENCE = 0.75
CAMERA_INDEX   = 0
FLIP_CAMERA    = True
THUMB_THRESH   = 0.50   # Bu değeri ayarlayarak baş parmak hassasiyetini değiştir

mp_hands = mp.solutions.hands
hands    = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=MIN_CONFIDENCE,
    min_tracking_confidence=0.65,
)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
f  = cv2.FONT_HERSHEY_SIMPLEX
fb = cv2.FONT_HERSHEY_DUPLEX

print("Calisıyor — Q ile cikis")
print(f"Bas parmak esigi: {THUMB_THRESH}  (kodu acip THUMB_THRESH degerini degistir)")

while True:
    ret, frame = cap.read()
    if not ret: break
    if FLIP_CAMERA: frame = cv2.flip(frame, 1)

    rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks:
        hand_lm   = results.multi_hand_landmarks[0]
        hand_info = results.multi_handedness[0]
        lm        = hand_lm.landmark
        side      = hand_info.classification[0].label
        conf      = hand_info.classification[0].score

        mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)

        # Baş parmak — mesafe tabanlı
        thumb_tip  = np.array([lm[4].x,  lm[4].y])
        index_mcp  = np.array([lm[5].x,  lm[5].y])
        wrist_pt   = np.array([lm[0].x,  lm[0].y])
        pinky_mcp  = np.array([lm[17].x, lm[17].y])
        hand_width = np.linalg.norm(wrist_pt - pinky_mcp) + 1e-6
        thumb_dist = np.linalg.norm(thumb_tip - index_mcp) / hand_width
        thumb_open = thumb_dist > THUMB_THRESH

        # Diğer 4 parmak
        finger_states = [thumb_open]
        for tip in [8, 12, 16, 20]:
            finger_states.append(lm[tip].y < lm[tip-2].y)

        total = sum(finger_states)

        # Panel
        cv2.rectangle(frame, (10, 10), (10+340, 10+240), (20,20,20), -1)
        cv2.rectangle(frame, (10, 10), (10+340, 10+240), (80,80,80), 1)

        cv2.putText(frame, f"El: {side}  ({conf:.0%})",
                    (20, 38), fb, 0.55, (240,240,240), 1)

        names = ["Bas parmak", "Isaret", "Orta", "Yuzuk", "Serce"]
        for i, (name, state) in enumerate(zip(names, finger_states)):
            color = (80,200,80) if state else (80,80,220)
            cv2.putText(frame, f"{name}: {'ACIK' if state else 'KAPALI'}",
                        (20, 68 + i*26), f, 0.48, color, 1)

        # Toplam — büyük rakam
        cv2.putText(frame, str(total), (280, 200), fb, 3.5, (50,180,230), 3, cv2.LINE_AA)

        # Baş parmak mesafe göstergesi (alt)
        H, W = frame.shape[:2]
        bar_w = 300
        bar_x, bar_y = 20, H - 55
        # Arka plan bar
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x+bar_w, bar_y+14), (60,60,60), -1)
        # Dolu kısım
        fill = min(1.0, thumb_dist / 0.8)
        col  = (80,200,80) if thumb_open else (80,80,220)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x+int(bar_w*fill), bar_y+14), col, -1)
        # Eşik çizgisi
        thresh_x = bar_x + int(bar_w * (THUMB_THRESH/0.8))
        cv2.line(frame, (thresh_x, bar_y-4), (thresh_x, bar_y+18), (255,255,255), 2)
        cv2.putText(frame,
                    f"Bas parmak mesafe: {thumb_dist:.3f}  esik:{THUMB_THRESH}  "
                    f"({'ACIK' if thumb_open else 'KAPALI'})",
                    (bar_x, H - 10), f, 0.38, (200,200,200), 1)

    else:
        cv2.putText(frame, "El bulunamadi", (40, 60), fb, 0.8, (80,80,220), 1)

    cv2.imshow("Finger Debug v2", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()