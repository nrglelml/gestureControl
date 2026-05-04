"""
Sadece baş parmak debug — sağ el için THUMB_OPEN_RATIO ayarı
Çalıştır: python debug_thumb.py
"""
import cv2, mediapipe as mp, numpy as np

CAMERA_INDEX = 0
FLIP         = True
CURRENT_THRESH = 0.32   # Mevcut eşik

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1,
                       min_detection_confidence=0.75,
                       min_tracking_confidence=0.70)
mp_draw = mp.solutions.drawing_utils
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
f  = cv2.FONT_HERSHEY_SIMPLEX
fb = cv2.FONT_HERSHEY_DUPLEX

print("Sag elini kameraya tut, 5 parmak ac.")
print("Alt barda ratio degerini not al, sonra THUMB_OPEN_RATIO'yu o degere ayarla.")

while True:
    ret, frame = cap.read()
    if not ret: break
    if FLIP: frame = cv2.flip(frame, 1)
    H, W = frame.shape[:2]

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = hands.process(rgb)

    if res.multi_hand_landmarks:
        lm   = res.multi_hand_landmarks[0].landmark
        side = res.multi_handedness[0].classification[0].label

        mp_draw.draw_landmarks(frame, res.multi_hand_landmarks[0],
                               mp_hands.HAND_CONNECTIONS)

        # Baş parmak ratio hesapla
        tip  = np.array([lm[4].x, lm[4].y])
        ip   = np.array([lm[5].x, lm[5].y])   # işaret MCP
        w0   = np.array([lm[0].x, lm[0].y])
        p17  = np.array([lm[17].x,lm[17].y])
        hw   = np.linalg.norm(w0 - p17) + 1e-6
        ratio = np.linalg.norm(tip - ip) / hw
        thumb_open = ratio > CURRENT_THRESH

        # Diğer 4 parmak
        TIPS = [8,12,16,20]
        PIPS = [6,10,14,18]
        others = [lm[t].y < lm[p].y for t,p in zip(TIPS,PIPS)]
        total = int(thumb_open) + sum(others)

        # Panel
        cv2.rectangle(frame,(8,8),(320,220),(20,20,20),-1)
        cv2.rectangle(frame,(8,8),(320,220),(80,80,80),1)
        cv2.putText(frame,f"El: {side}",(18,36),fb,0.55,(240,240,240),1)
        names = ["Bas parmak","Isaret","Orta","Yuzuk","Serce"]
        states = [thumb_open]+others
        for i,(name,st) in enumerate(zip(names,states)):
            col = (80,200,80) if st else (80,80,220)
            cv2.putText(frame,f"{name}: {'ACIK' if st else 'KAPALI'}",
                        (18,62+i*26),f,0.46,col,1)

        # Büyük sayı
        cv2.putText(frame,str(total),(258,185),fb,3.0,(50,180,230),3,cv2.LINE_AA)

        # Ratio bar (alt)
        bx,by,bw,bh = 10, H-60, 400, 18
        cv2.rectangle(frame,(bx,by),(bx+bw,by+bh),(60,60,60),-1)
        fill = min(1.0, ratio/0.6)
        col  = (80,200,80) if thumb_open else (80,80,220)
        cv2.rectangle(frame,(bx,by),(bx+int(bw*fill),by+bh),col,-1)
        # Eşik çizgisi
        tx = bx + int(bw*(CURRENT_THRESH/0.6))
        cv2.line(frame,(tx,by-5),(tx,by+bh+5),(255,255,0),2)
        cv2.putText(frame,
            f"Ratio: {ratio:.3f}  esik:{CURRENT_THRESH}  "
            f"({'ACIK' if thumb_open else 'KAPALI'})",
            (bx,H-12),f,0.38,(200,200,200),1)

        # Kapalıyken ve açıkken ratio değerlerini göster
        cv2.putText(frame,"Bas parmak KAPALI: ratio kac? (sol altta bak)",
                    (8,H-82),f,0.34,(180,180,80),1)

    else:
        cv2.putText(frame,"El bulunamadi",(40,60),fb,0.8,(80,80,220),1)

    cv2.imshow("Thumb Debug",frame)
    if cv2.waitKey(1)&0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()