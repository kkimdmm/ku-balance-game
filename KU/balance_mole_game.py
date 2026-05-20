"""
Balance Mole Game — Streamlit 버전
CAI 발목불안정성 재활 프로그램

실행:
  pip install streamlit opencv-python mediapipe pillow
  streamlit run balance_mole_streamlit.py
"""

import streamlit as st
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image
import math, time, random, datetime, os, csv, threading
import csv, time, os
import datetime
import random
import numpy as np
import threading
import pygame

# pygame 믹서 초기화 (앱 시작 시 한 번만)
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

def _make_sound(wave: np.ndarray, volume=0.6) -> pygame.mixer.Sound:
    wave = np.clip(wave, -1.0, 1.0)
    pcm  = (wave * 32767).astype(np.int16)
    # stereo 믹서 대응: (N,) → (N, 2) 로 복제
    pcm_stereo = np.column_stack([pcm, pcm])
    return pygame.sndarray.make_sound(pcm_stereo)

def _play_async(sound: pygame.mixer.Sound):
    """메인 스레드 블로킹 없이 재생"""
    threading.Thread(target=sound.play, daemon=True).start()

# ── 효과음 미리 생성 (앱 로드 시 1회) ──────────────────────────

SR = 44100  # 샘플레이트

def _build_success_sound():
    """뿅뿅: 짧은 상승 톤 2연타"""
    sounds = []
    for freq in [600, 900]:          # 낮은 음 → 높은 음
        t = np.linspace(0, 0.10, int(SR * 0.10))
        wave = np.sin(2 * np.pi * freq * t)
        env  = np.exp(-t * 18)       # 빠른 감쇠 → 뿅 느낌
        sounds.append(wave * env)
    gap  = np.zeros(int(SR * 0.04))  # 40ms 간격
    full = np.concatenate([sounds[0], gap, sounds[1]])
    return _make_sound(full * 0.7)

def _build_fail_sound():
    """폭탄: 저주파 노이즈 버스트 + 하강 톤"""
    t_noise = np.linspace(0, 0.12, int(SR * 0.12))
    noise   = np.random.uniform(-1, 1, len(t_noise))
    env_n   = np.exp(-t_noise * 12)
    burst   = noise * env_n * 0.9    # 폭발 노이즈

    t_fall  = np.linspace(0, 0.18, int(SR * 0.18))
    freq    = np.linspace(350, 80, len(t_fall))   # 주파수 하강
    wave    = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    env_f   = np.exp(-t_fall * 8)
    fall    = wave * env_f * 0.8

    gap  = np.zeros(int(SR * 0.02))
    full = np.concatenate([burst, gap, fall])
    return _make_sound(full)

# 앱 시작 시 미리 빌드
SFX_SUCCESS = _build_success_sound()
SFX_FAIL    = _build_fail_sound()

# ─────────────────────────────────────────────────────────────
#  페이지 설정
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Balance Mole Game · CAI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
#  CSS 스타일
# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
#  CSS 스타일 (전체 배경 블랙 + 타이틀 민트 + 버튼 그라데이션)
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Noto+Sans+KR:wght@400;700&display=swap');

/* 1. 전체 배경색 (검정) */
.stApp {
    background-color: #000000 !important;
    color: #ECF0F1;
    font-family: 'Noto Sans KR', sans-serif;
}

/* 헤더/푸터 숨기기 */
#MainMenu, header, footer { visibility: hidden; }

/* 2. 메인 타이틀 (민트색) */
.title-main { 
    font-family: 'Share Tech Mono', monospace; 
    font-size: 4.5em; 
    font-weight: bold;
    color: #4DB6AC !important; /* 민트색 */
    text-align: center;
    text-shadow: 2px 2px 10px rgba(77, 182, 172, 0.4);
    margin-bottom: 0px;
}

/* 3. 사이버펑크 네온 그라데이션 버튼 */
.stButton > button {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 18px !important;
    font-weight: bold !important;
    border-radius: 12px !important;
    padding: 12px 28px !important;
    color: #FFFFFF !important;
    
    /* 기본 상태: 은은한 메탈릭-민트 그라데이션 */
    background: linear-gradient(135deg, #004D40 0%, #00241F 100%) !important;
    border: 1px solid #4DB6AC !important;
    box-shadow: 0 0 8px rgba(77, 182, 172, 0.2) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* 🔥 마우스를 올렸을 때 (Hover): 네온 조명이 켜지며 강렬하게 빛나는 효과 */
.stButton > button:hover {
    color: #000000 !important; /* 글자색을 검정으로 바꿔 대비감 극대화 */
    transform: translateY(-3px) scale(1.02) !important; /* 살짝 떠오르고 커지는 효과 */
    
    /* 활활 타오르는 민트-블루 그라데이션 */
    background: linear-gradient(135deg, #4DB6AC 0%, #00B0FF 100%) !important;
    border: 1px solid #00E5FF !important;
    
    /* 💥 핵심: 다중 그림자로 번지는 듯한 네온(Glow) 효과 구현 */
    box-shadow: 0 0 15px #4DB6AC, 
                0 0 30px rgba(0, 229, 255, 0.6), 
                0 4px 20px rgba(0, 0, 0, 0.5) !important;
}

/* ⚡ 클릭하는 순간 (Active): 버튼이 꾹 눌리며 스파크가 튀는 듯한 효과 */
.stButton > button:active {
    transform: translateY(-1px) scale(0.98) !important; /* 꾹 눌리는 물리적 느낌 */
    background: linear-gradient(135deg, #00E5FF 0%, #4DB6AC 100%) !important;
    box-shadow: 0 0 25px #00E5FF, 
                0 0 50px rgba(77, 182, 172, 0.8) !important;
    transition: all 0.05s !important;
}

/* 4-1. NORMAL 카드 디자인 (블루 네온 림) */
.card-normal {
    background: rgba(10, 16, 26, 0.9) !important;  /* 은은한 다크 블루 블랙 */
    border: 1px solid #00D5FF !important;          /* 선명한 시안 블루 테두리 ⭐ */
    border-radius: 16px !important;
    padding: 25px !important;
    margin-bottom: 20px !important;
    /* 블루 네온 그라데이션 광무늬 효과 */
    box-shadow: 0 0 15px rgba(0, 213, 255, 0.15), inset 0 0 15px rgba(0, 213, 255, 0.05) !important;
}

/* 4-2. HARD 카드 디자인 (레드 네온 림) */
.card-hard {
    background: rgba(26, 10, 10, 0.9) !important;  /* 은은한 다크 레드 블랙 */
    border: 1px solid #FF4D4D !important;          /* 강렬한 레드 테두리 ⭐ */
    border-radius: 16px !important;
    padding: 25px !important;
    margin-bottom: 20px !important;
    /* 레드 네온 그라데이션 광무늬 효과 */
    box-shadow: 0 0 15px rgba(255, 77, 77, 0.15), inset 0 0 15px rgba(255, 77, 77, 0.05) !important;
}

/* 5. 카드 내부의 리스트 텍스트(어두운 글씨) 선명하게 수정 */
.card ul, .card li {
    color: #E2E8F0 !important;   /* 어두운 회색에서 선명한 연회색으로 변경 */
    font-size: 15px !important;
    line-height: 1.8 !important;
}

/* 6. 폭탄 모드 선택창 하단의 라디오 버튼 글씨 선명하게 수정 */
.stRadio div[data-testid="stMarkdownContainer"] p {
    color: #FFFFFF !important;   /* 라디오 버튼 선택지 글씨 완벽한 흰색 고정 */
    font-size: 15px !important;
    font-weight: 500 !important;
}

/* 7. '평가 종류' 같은 작은 서브 라벨 글씨 수정 */
.stRadio > label, div[data-testid="stWidgetLabel"] p {
    color: #94A3B8 !important;   /* 은은하고 세련된 블루그레이 색상 */
    font-size: 14px !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  상수
# ─────────────────────────────────────────────────────────────
CAM_W, CAM_H = 640, 480
CIRCLE_POS = [
    (0.20, 0.18), (0.40, 0.12), (0.60, 0.12), (0.80, 0.18),
    (0.12, 0.42), (0.35, 0.38), (0.65, 0.38), (0.88, 0.42),
    (0.15, 0.68), (0.38, 0.72), (0.62, 0.72), (0.85, 0.68),
]
CIRCLE_R = 28
GAME_DUR = 50

C = {
    "bg":      (7,   8,  13),
    "acc":     (79, 142, 255),
    "green":   (46, 204, 113),
    "yellow":  (241, 196,  15),
    "red":     (231,  76,  60),
    "orange":  (230, 126,  34),
    "muted":   (86,  101, 115),
    "cyan":    (26, 188, 156),
    "hot":     (255, 107,  53),
    "touched": (255, 215,   0),
}

def bgr(name):
    r, g, b = C[name]
    return (b, g, r)

# ─────────────────────────────────────────────────────────────
#  TTS (비동기)
# ─────────────────────────────────────────────────────────────
def _speak(text):
    def _r():
        try:
            import pyttsx3
            e = pyttsx3.init()
            e.setProperty("rate", 155)
            e.say(text)
            e.runAndWait()
            e.stop()
        except Exception:
            pass
    threading.Thread(target=_r, daemon=True).start()

# ─────────────────────────────────────────────────────────────
#  세션 상태 초기화
# ─────────────────────────────────────────────────────────────
def init_state():
    defaults = dict(
        phase          = "login",      # login | ready | countdown | playing | result
        pid            = "Tester_01",  # 피험자 식별용 ID 추가 ⭐
        logger         = None,         # 로거 객체 저장용 추가 ⭐
        trial_counter  = 0,            # 몇 번째 두더지인지 카운트 추가 ⭐
        mode           = None,
        score          = 0,
        combo          = 0,
        lit_set        = set(),
        touch_cd       = {},
        flash_until    = {},
        game_start     = None,
        last_mole_t    = 0.0,
        mole_interval  = 1.5,
        num_lit        = 1,
        countdown_n    = 3,
        countdown_last = 0.0,
        fail_reason    = "",
        session_rows   = [],
        session_id     = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
        feedback_text  = "손을 뻗어 원에 닿으세요!",
        combo_text     = "",
        pose_status    = "카메라 확인 중…",
        cap_index      = 0,
        # 인지 재활 모드 추가: "SIMPLE" (모두 점수) / "COLOR" (초록만 점수, 빨강은 폭탄) ⭐
        cog_mode       = "COLOR", 
        # 화면에 켜진 두더지들의 색상 상태를 저장할 딕셔너리
        mole_colors    = {}, # 예: {0: "green", 3: "red"} ⭐
    )
    
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─────────────────────────────────────────────────────────────
#  MediaPipe  (세션당 1회 생성)
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_pose():
    return mp.solutions.pose.Pose(
        min_detection_confidence=0.55,
        min_tracking_confidence=0.55,
        model_complexity=1,
    )

pose_model = get_pose()

# ─────────────────────────────────────────────────────────────
#  카메라 (세션당 1회 유지)
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_cap(index=0):
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    return cap

cap = get_cap(st.session_state.cap_index)

# ─────────────────────────────────────────────────────────────
#  유틸
# ─────────────────────────────────────────────────────────────
def spawn_moles():
    ss = st.session_state
    ss.lit_set.clear()
    ss.mole_colors.clear() # 기존 색상 초기화 ⭐
    ss.last_mole_t = time.time()

    # 몇 개를 켤지 결정
    count = min(ss.num_lit, len(CIRCLE_POS))
    chosen_indices = random.sample(range(len(CIRCLE_POS)), count)

    for idx in chosen_indices:
        ss.lit_set.add(idx)
        
        # COLOR 모드일 때 30% 확률로 빨간색(폭탄) 부여 ⭐
        if ss.cog_mode == "COLOR" and random.random() < 0.3:
            ss.mole_colors[idx] = "red"
        else:
            ss.mole_colors[idx] = "green" # 일반 두더지는 초록색

def grade(score, mode):
    base = score if mode == "normal" else score * 0.8
    if base >= 150: return "S  완벽!",  "grade-s"
    if base >= 100: return "A  훌륭해!", "grade-a"
    if base >=  60: return "B  좋아요!", "grade-b"
    if base >=  30: return "C  연습 필요","grade-c"
    return "D  계속 도전!", "grade-d"

def save_csv():
    ss = st.session_state
    try:
        path = os.path.expanduser(f"~/balance_mole_{ss.session_id}.csv")
        keys = ["session_id", "mode", "score", "duration_s", "fail_reason", "timestamp"]
        with open(path, "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.DictWriter(fp, fieldnames=keys)
            w.writeheader()
            w.writerows(ss.session_rows)
        return path
    except Exception as e:
        return None

def reset_to_login():
    keys_to_keep = {"cap_index", "session_id", "session_rows"}
    for k in list(st.session_state.keys()):
        if k not in keys_to_keep:
            del st.session_state[k]
    init_state()
    st.session_state.phase = "login"

# ─────────────────────────────────────────────────────────────
#  카메라 프레임 읽기 + 포즈 처리
# ─────────────────────────────────────────────────────────────
def read_frame_with_pose():
    """
    Returns: (frame_rgb, result, hand_pts)
    frame_rgb: numpy array HxWx3 (RGB)
    result:    mediapipe pose result
    hand_pts:  list of (x,y) pixel coords for hands
    """
    ret, frame = cap.read()
    if not ret:
        blank = np.zeros((CAM_H, CAM_W, 3), dtype=np.uint8)
        return blank, None, []

    frame  = cv2.flip(frame, 1)
    result = pose_model.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    h, w   = frame.shape[:2]
    hand_pts = []

    if result.pose_landmarks:
        lm = result.pose_landmarks.landmark

        def px(i):
            return (int(lm[i].x * w), int(lm[i].y * h))

        # 관절 연결선
        connections = [
            (11,12),(11,23),(12,24),(23,24),
            (23,25),(24,26),(25,27),(26,28),
            (11,13),(13,15),(12,14),(14,16),
            (15,19),(16,20),
        ]
        for a, b in connections:
            try:
                cv2.line(frame, px(a), px(b), (60, 70, 100), 2)
            except Exception:
                pass

        # 주요 관절 점
        key_colors = {
            11: bgr("acc"),  12: bgr("acc"),
            23: bgr("green"),24: bgr("green"),
            25: bgr("yellow"),26: bgr("yellow"),
            27: bgr("orange"),28: bgr("orange"),
            15: bgr("cyan"), 16: bgr("cyan"),
            19: bgr("cyan"), 20: bgr("cyan"),
        }
        sizes = {11:5,12:5,23:6,24:6,25:7,26:7,27:6,28:6,15:7,16:7,19:8,20:8}
        for ji, jc in key_colors.items():
            try:
                cv2.circle(frame, px(ji), sizes.get(ji,5), jc, -1)
            except Exception:
                pass

        # 손 점
        for hi in [15, 16, 19, 20]:
            try:
                hand_pts.append(px(hi))
            except Exception:
                pass
        for hp in hand_pts:
            cv2.circle(frame, hp, 8,  (0, 230, 200), -1)
            cv2.circle(frame, hp, 12, (0, 230, 200), 2)

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return frame_rgb, result, hand_pts

# ─────────────────────────────────────────────────────────────
#  두더지 원 그리기
# ─────────────────────────────────────────────────────────────
def draw_circles(frame_rgb, hand_pts):
    ss  = st.session_state
    now = time.time()
    h, w = frame_rgb.shape[:2]
    
    for i, (rx, ry) in enumerate(CIRCLE_POS):
        cx = int(rx * w)
        cy = int(ry * h)
        lit      = i in ss.lit_set

        # ─── 1. 두더지 색상 결정 ─── ⭐
        # ✅ flash 판정 추가 (터치 성공 직후 0.35초간 빛남)
        flashing = i in ss.flash_until and now < ss.flash_until[i]

        if flashing:
            # 터치 성공 플래시 — 이전에 green이었으면 노란 섬광, red였으면 주황 섬광
            prev_color = ss.mole_colors.get(i, "green")
            if prev_color == "green":
                circle_color = (255, 255, 0)   # 노란 섬광
                col_bg       = (180, 180, 0)
            else:
                circle_color = (255, 140, 0)   # 주황 섬광 (폭탄 터짐)
                col_bg       = (160, 80, 0)
            text_label = "✓" if prev_color == "green" else "💥"

        elif lit:
            current_color = ss.mole_colors.get(i, "green")
            if current_color == "red":
                circle_color = (255, 0, 0)       # OpenCV BGR 순서 (빨간색 본체)
                col_bg   = (130, 0, 0)       # 선명한 빨간색 기반 배경/글자용 색상
                text_label = "BOMB"
            else:
                circle_color = (0, 255, 0)       # 초록색 본체
                col_bg   = (0, 130, 0)       # 선명한 초록색 기반 배경/글자용 색상
                text_label = "TARGET"
        else:
            circle_color = (120, 120, 120)       # 꺼진 상태 (약간 밝은 회색으로 조정)
            col_bg   = (60, 60, 60)          # 어두운 회색
            text_label = ""

        # ── 입체 버튼 스타일 원 그리기 ──────────────────────────────
        R = CIRCLE_R

        # 1) 하단 그림자 (col_bg 변수를 망가뜨리지 않게 전용 변수 shadow_bg 사용!) ⭐
        shadow_bg = (col_bg[0]//2, col_bg[1]//2, col_bg[2]//2)
        cv2.circle(frame_rgb, (cx + 2, cy + 4), R, shadow_bg, -1)

        # 2) 메인 원 (베이스 색 채우기 및 라벨링)
        cv2.circle(frame_rgb, (cx + 3, cy + 3), CIRCLE_R, shadow_bg, -1 if lit else 2) 
        cv2.circle(frame_rgb, (cx, cy), CIRCLE_R, circle_color, -1 if lit else 2)
        
        # TARGET / BOMB 글자 표시
        if text_label:
            cv2.putText(frame_rgb, text_label, (cx - 25, cy + 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # 3) 하단 어두운 반원 (입체감 아래쪽 입체 음영)
        dark_col = (max(0, col_bg[0]-40), max(0, col_bg[1]-40), max(0, col_bg[2]-40))
        pts_bottom = cv2.ellipse2Poly((cx, cy), (R, R), 0, 10, 170, 5)
        cv2.fillPoly(frame_rgb, [pts_bottom], dark_col)

        # 4) 상단 밝은 반원 (입체감 위쪽 하이라이트)
        light_col = (min(255, col_bg[0]+80), min(255, col_bg[1]+80), min(255, col_bg[2]+80))
        pts_top = cv2.ellipse2Poly((cx, cy - 3), (R - 4, R // 2), 0, 190, 350, 5)
        cv2.fillPoly(frame_rgb, [pts_top], light_col)

        # 5) 테두리 림(rim) -> 원본의 색상 왜곡 버그 수정
        cv2.circle(frame_rgb, (cx, cy), R, circle_color, 2)

        # 6) 광택 작은 원 (왼쪽 상단)
        shine_x = cx - R // 3
        shine_y = cy - R // 3
        cv2.circle(frame_rgb, (shine_x, shine_y), R // 5, (255, 255, 255), -1) # 흰색 광택으로 선명하게! ⭐

        # 7) 숫자 텍스트 (배경색 col_bg를 활용해 입체감 구현, 검은색/흰색 대비로 가독성 확보) ⭐
        # 테두리 그림자 효과
        cv2.putText(frame_rgb, str(i + 1), (cx - 6 + 1, cy + 6 + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
        # 메인 숫자 (꺼졌을 땐 어두운 색, 켜졌을 땐 선명한 흰색으로 가독성 극대화)
        text_color = (255, 255, 255) if lit else (200, 200, 200)
        cv2.putText(frame_rgb, str(i + 1), (cx - 6, cy + 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, text_color, 2)
                    
        # ─── 3. 터치 판정 및 점수 계산 (기존 로직 완벽 유지) ───
        if lit and i not in ss.touch_cd:
            for hp in hand_pts:
                if math.hypot(hp[0] - cx, hp[1] - cy) < CIRCLE_R + 10:
                    ss.touch_cd[i]    = now
                    ss.flash_until[i] = now + 0.35
                    ss.lit_set.discard(i)
                    ss.trial_counter += 1
                    rt_ms = int((now - ss.last_mole_t) * 1000)

                    chosen_color = ss.mole_colors.get(i, "green")

                    if chosen_color == "green":
                        ss.score += 5
                        ss.combo += 1
                        ss.feedback_text = f"+5점! (정상 타겟)"
                        is_success = True
                        _play_async(SFX_SUCCESS)   # ← 뿅뿅
                    else:
                        ss.score = max(0, ss.score - 5)
                        ss.combo = 0                     
                        ss.feedback_text = f"💥 폭탄 터짐! -5점"
                        is_success = False               
                        _play_async(SFX_FAIL)      # ← 폭탄 효과음

                    if ss.logger:
                        ss.logger.log(
                            trial_num=ss.trial_counter,
                            button_id=i + 1,
                            reaction_ms=rt_ms,
                            success=is_success, 
                            diff_level=f"{ss.mode}_{ss.cog_mode}",
                            balance_lost=False
                        )
                    break
    # 쿨다운 만료
    expired = [i for i, t in ss.touch_cd.items() if now - t > 0.8]
    for i in expired:
        del ss.touch_cd[i]

    return frame_rgb

class SessionLogger:
    def __init__(self, participant_id: str):
        self.pid = participant_id
        self.session_start = time.time()
        self.trials = []
        os.makedirs("data", exist_ok=True)
        self.filename = f"data/{participant_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._write_header()

    def _write_header(self):
        with open(self.filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "trial", "timestamp", "elapsed_sec",
                "button_id", "reaction_time_ms",
                "success", "difficulty_level",
                "balance_lost"  # 발 내딛음 여부
            ])

    def log(self, trial_num, button_id, reaction_ms,
            success, diff_level, balance_lost=False):
        row = [
            trial_num,
            datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
            round(time.time() - self.session_start, 2),
            button_id, reaction_ms, success,
            diff_level, balance_lost
        ]
        self.trials.append(row)
        with open(self.filename, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

    def summary(self):
        if not self.trials:
            return {}
        hits = [t for t in self.trials if t[5]]  # success == True
        rts = [t[4] for t in hits]
        return {
            "total_trials": len(self.trials),
            "accuracy": round(len(hits) / len(self.trials) * 100, 1),
            "mean_RT_ms": round(sum(rts)/len(rts), 1) if rts else 0,
            "balance_failures": sum(1 for t in self.trials if t[7]),
            "final_level": self.trials[-1][6]
        }
# ─────────────────────────────────────────────────────────────
#  ① 로그인 / 모드 선택 화면
# ─────────────────────────────────────────────────────────────
def page_login():
    # ─── 🎨 상단 로고 & 타이틀 영역 ───
    st.markdown("""
    <div style='text-align:center; padding: 20px 0 10px 0;'>
        <img src='https://raw.githubusercontent.com/kkimdmm/20260114_KU_Vibe/master/Gemini_Generated_Image_b9hnb5b9hnb5b9hn.png' style='
            width: 320px; 
            height: auto; 
            margin-bottom: -10px;
            filter: drop-shadow(0 0 15px rgba(22, 255, 210, 0.25)); /* 민트색 글로우 효과 */
        '>
        <div class='title-main'>BALANCE GAME</div>
        <div class='title-sub'>한발서기 두더지 게임 &nbsp;·&nbsp; CAI 발목 재활 프로그램</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_l, col_r = st.columns(2, gap="large")
    st.markdown("### 💣 폭탄 모드 선택")
    st.session_state.cog_mode = st.radio(
        "평가 종류",
        ["SIMPLE (일반 한발서기)", "COLOR (선택적 주의력 - 초록만 터치, 빨강은 폭탄)"],
        index=1
    )
    # 실제 변수 값만 추출하기 위한 매핑
    if "SIMPLE" in st.session_state.cog_mode:
        st.session_state.cog_mode = "SIMPLE"
    else:
        st.session_state.cog_mode = "COLOR"


    with col_l:
        st.markdown("""
        <div class='card-normal'>
            <div style='color: #00D5FF; font-family: "Share Tech Mono"; font-size: 14px;'>Mode 01</div>
            <h2 style='color: #00B0FF; margin-top: 5px; font-family: "Share Tech Mono";'>NORMAL</h2>
            <div style='color: #FFFFFF; font-weight: bold; margin-bottom: 15px;'>일반 모드</div>
            <ul>
                ⏱&nbsp; 50초 게임<br>
                ▷&nbsp; 두더지 1개씩 등장<br>
                ▷&nbsp; 1.5초마다 이동<br>
                ▷&nbsp; 한발서기 유지
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("▶  NORMAL 시작", key="btn_normal",
                     use_container_width=True):
            _play_async(SFX_SUCCESS)   # ← 뿅뿅
            st.session_state.mode          = "normal"
            st.session_state.mole_interval = 1.5
            st.session_state.num_lit       = 1
            # 로거 객체 생성 및 세션 저장 ⭐
            st.session_state.logger        = SessionLogger(st.session_state.pid)
            st.session_state.trial_counter = 0
            st.session_state.phase         = "ready"
            _speak("노말 모드. 한발서기로 무릎이 골반 기준선에 닿으면 시작합니다.")
            st.rerun()

    with col_r:
        st.markdown("""
        <div class='card-hard'>
            <div style='color: #FF4D4D; font-family: "Share Tech Mono"; font-size: 14px;'>Mode 02</div>
            <h2 style='color: #FF4D4D; margin-top: 5px; font-family: "Share Tech Mono";'>HARD</h2>
            <div style='color: #FFFFFF; font-weight: bold; margin-bottom: 15px;'>하드 모드</div>
            <ul>
                ⏱&nbsp; 50초 게임<br>
                ▷&nbsp; 두더지 2개 동시 등장<br>
                ▷&nbsp; 1.3초마다 이동<br>
                ▷&nbsp; 한발서기 + 빠른 반응
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("▶  HARD 시작", key="btn_hard",
                     use_container_width=True):
            _play_async(SFX_SUCCESS)   # ← 뿅뿅
            st.session_state.mode          = "hard"
            st.session_state.mole_interval = 1.0
            st.session_state.num_lit       = 2
            # 로거 객체 생성 및 세션 저장 ⭐
            st.session_state.logger        = SessionLogger(st.session_state.pid)
            st.session_state.trial_counter = 0
            st.session_state.phase         = "ready"
            _speak("하드 모드. 한발서기로 무릎이 골반 기준선에 닿으면 시작합니다.")
            st.rerun()

    st.markdown("""
    <div style='text-align:center; margin-top:30px; color:#566573; font-size:12px;'>
        ⚑&nbsp; 한발서기 → 무릎을 골반선에 닿게 하면 게임이 자동 시작됩니다
    </div>
    """, unsafe_allow_html=True)

    # 스타일: Normal/Hard 버튼 색상
    st.markdown("""
    <style>
    div[data-testid="column"]:nth-child(1) .stButton>button {
        background-color: #4F8EFF; color: #000; width: 100%;
    }
    div[data-testid="column"]:nth-child(2) .stButton>button {
        background-color: #E74C3C; color: #fff; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  ② 준비 화면 (한발서기 감지)
# ─────────────────────────────────────────────────────────────
def page_ready():
    ss    = st.session_state
    color = "#4F8EFF" if ss.mode == "normal" else "#E74C3C"
    badge = "badge-normal" if ss.mode == "normal" else "badge-hard"
    mode_label = "NORMAL" if ss.mode == "normal" else "HARD"

    # 헤더
    st.markdown(f"""
    <div style='display:flex; align-items:center; gap:10px; margin-bottom:8px;'>
        <span class='{badge}'>{mode_label}</span>
        <span style='color:#566573; font-family:Share Tech Mono,monospace; font-size:13px;'>
            준비 — 한발서기 자세를 취하세요
        </span>
    </div>
    """, unsafe_allow_html=True)

    cam_col, info_col = st.columns([3, 1], gap="small")

    with info_col:
        st.markdown(f"""
        <div class='card'>
            <div class='label-sm'>시작 조건</div>
            <div style='font-family:Share Tech Mono,monospace; font-size:16px; font-weight:bold; color:{color}; margin:6px 0 4px;'>무릎 → 골반선</div>
            <div style='color:#566573; font-size:12px; line-height:1.8;'>
                한발서기 상태로<br>무릎을 골반 높이<br>기준선에 닿게 하세요
            </div>
        </div>
        <div class='card'>
            <div class='label-sm'>자세 상태</div>
            <div id='state-lbl' style='font-family:Share Tech Mono,monospace; font-size:14px; font-weight:bold; color:{color}; margin-top:6px;'>
                {ss.pose_status}
            </div>
        </div>
        <div class='card'>
            <div class='label-sm'>게임 규칙</div>
            <div style='color:#566573; font-size:12px; line-height:1.8; margin-top:6px;'>
                ⏱ 50초 게임<br>🎯 불 켜진 원에 손 대기<br>✋ 5점 획득
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("← 모드 선택", key="btn_back_ready"):
            reset_to_login()
            st.rerun()

    with cam_col:
        frame_rgb, result, hand_pts = read_frame_with_pose()
        h, w = frame_rgb.shape[:2]
        start_trigger = False

        if result and result.pose_landmarks:
            lm = result.pose_landmarks.landmark

            def px(i):
                return (int(lm[i].x * w), int(lm[i].y * h))

            l_hip  = px(23); r_hip  = px(24)
            l_knee = px(25); r_knee = px(26)
            l_ank  = px(27); r_ank  = px(28)

            base_y = (l_hip[1] + r_hip[1]) // 2
            cv2.line(frame_rgb, (0, base_y), (w, base_y), (70, 130, 220), 2)
            cv2.putText(frame_rgb, "BASELINE", (10, base_y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (70, 130, 220), 1)

            l_up = l_ank[1] < r_ank[1] - 40
            r_up = r_ank[1] < l_ank[1] - 40

            knee_in_zone = False
            if l_up and abs(l_knee[1] - base_y) < 40:
                knee_in_zone = True
            elif r_up and abs(r_knee[1] - base_y) < 40:
                knee_in_zone = True

            lkc = (50, 220, 130) if (l_up and knee_in_zone) else ((0, 180, 255) if l_up else (100,100,100))
            rkc = (50, 220, 130) if (r_up and knee_in_zone) else ((0, 180, 255) if r_up else (100,100,100))
            cv2.circle(frame_rgb, l_knee, 10, lkc, 2)
            cv2.circle(frame_rgb, r_knee, 10, rkc, 2)

            if knee_in_zone:
                cv2.putText(frame_rgb, "START!", (w//2 - 70, 65),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (50, 220, 130), 3)
                start_trigger = True
                ss.pose_status = "✔ 시작 조건 충족!"
            elif l_up or r_up:
                ss.pose_status = "무릎을 골반선 높이로!"
            else:
                ss.pose_status = "한발을 들어 올리세요"
        else:
            ss.pose_status = "전신을 카메라에"

        st.image(frame_rgb, channels="RGB", use_container_width=True)

        if start_trigger:
            ss.phase         = "countdown"
            ss.countdown_n   = 3
            ss.countdown_last = time.time() - 1.0  # 즉시 첫 틱
            _speak("3")
            time.sleep(0.3)
            st.rerun()
        else:
            time.sleep(0.05)
            st.rerun()

# ─────────────────────────────────────────────────────────────
#  ③ 카운트다운 화면
# ─────────────────────────────────────────────────────────────
def page_countdown():
    ss    = st.session_state
    color = "#4F8EFF" if ss.mode == "normal" else "#E74C3C"
    n     = ss.countdown_n
    label = str(n) if n > 0 else "GO!"

    st.markdown(f"""
    <div style='text-align:center; padding:60px 0;'>
        <div style='font-family:Share Tech Mono,monospace; font-size:22px; font-weight:bold; color:{color};'>준비!</div>
        <div style='color:#566573; font-size:14px; margin:8px 0 20px;'>한발서기 자세 유지</div>
        <div style='font-family:Share Tech Mono,monospace; font-size:120px; font-weight:bold; color:{color}; line-height:1;'>{label}</div>
    </div>
    """, unsafe_allow_html=True)

    now = time.time()
    if now - ss.countdown_last >= 1.0:
        ss.countdown_last = now
        if ss.countdown_n > 0:
            ss.countdown_n -= 1
            if ss.countdown_n > 0:
                _speak(str(ss.countdown_n))
            else:
                _speak("시작!")
        else:
            # GO → 게임 시작
            ss.phase       = "playing"
            ss.score       = 0
            ss.combo       = 0
            ss.lit_set     = set()
            ss.touch_cd    = {}
            ss.flash_until = {}
            ss.game_start  = time.time()
            ss.last_mole_t = time.time()
            ss.feedback_text = "손을 뻗어 원에 닿으세요!"
            ss.combo_text    = ""
            spawn_moles()
            st.rerun()
            return

    time.sleep(0.1)
    st.rerun()

# ─────────────────────────────────────────────────────────────
#  ④ 게임 플레이 화면
# ─────────────────────────────────────────────────────────────
def page_playing():
    ss     = st.session_state
    now    = time.time()
    elapsed = now - ss.game_start
    remain  = max(0, GAME_DUR - int(elapsed))
    ratio   = min(elapsed / GAME_DUR, 1.3)

    color     = "#4F8EFF" if ss.mode == "normal" else "#E74C3C"
    badge     = "badge-normal" if ss.mode == "normal" else "badge-hard"
    mode_label = "NORMAL" if ss.mode == "normal" else "HARD"

    # 시간 초과
    if elapsed >= GAME_DUR:
        ss.fail_reason = "50초 완료!"
        ss.session_rows.append({
            "session_id": ss.session_id,
            "mode":       ss.mode,
            "score":      ss.score,
            "duration_s": int(elapsed),
            "fail_reason":"time",
            "timestamp":  datetime.datetime.now().isoformat(),
        })
        save_csv()
        ss.phase = "result"
        _speak(f"게임 완료! 최종 점수 {ss.score}점!")
        st.rerun()
        return

    # 두더지 이동
    if now - ss.last_mole_t > ss.mole_interval:
        spawn_moles()

    # 진행바 색
    if ratio > 0.75:
        bar_color = "#E74C3C"
    elif ratio > 0.5:
        bar_color = "#E67E22"
    else:
        bar_color = color

    # 헤더 / 점수 / 타이머
    st.markdown(f"""
    <div style='display:flex; align-items:center; gap:12px; margin-bottom:4px;'>
        <span class='{badge}'>{mode_label}</span>
        <span style='font-family:Share Tech Mono,monospace; font-size:20px; font-weight:bold; color:#F1C40F;'>
            SCORE: {ss.score}
        </span>
        <span style='flex:1;'></span>
        <span style='color:#566573; font-family:Share Tech Mono,monospace; font-size:13px;'>남은 시간 :</span>
        <span style='font-family:Share Tech Mono,monospace; font-size:22px; font-weight:bold; color:#ECF0F1;'>
            {remain}
        </span>
    </div>
    <div class='prog-outer'>
        <div class='prog-inner' style='width:{ratio*100:.1f}%; background:{bar_color};'></div>
    </div>
    """, unsafe_allow_html=True)

    cam_col, side_col = st.columns([3, 1], gap="small")

    with side_col:
        g_text, g_class = grade(ss.score, ss.mode)
        st.markdown(f"""
        <div class='card'>
            <div class='label-sm'>SCORE</div>
            <div style='font-family:Share Tech Mono,monospace; font-size:50px; font-weight:bold; color:#F1C40F; line-height:1.1;'>{ss.score}</div>
            <div style='font-family:Share Tech Mono,monospace; font-size:14px; font-weight:bold; color:#FF6B35;'>{ss.combo_text}</div>
        </div>
        <div class='card'>
            <div class='label-sm'>STATUS</div>
            <div style='font-family:Share Tech Mono,monospace; font-size:13px; font-weight:bold; color:#2ECC71; margin-top:6px;'>{ss.pose_status}</div>
        </div>
        <div class='card'>
            <div class='label-sm'>FEEDBACK</div>
            <div style='font-size:13px; color:#ECF0F1; margin-top:6px;'>{ss.feedback_text}</div>
        </div>
        """, unsafe_allow_html=True)

        if ss.mode == "hard":
            st.markdown("""
            <div class='card card-red' style='margin-top:8px;'>
                <div style='font-family:Share Tech Mono,monospace; font-size:12px; font-weight:bold; color:#E74C3C;'>⚡ HARD MODE</div>
                <div style='color:#566573; font-size:11px; margin-top:4px;'>두더지 2개 동시<br>1초마다 이동</div>
            </div>
            """, unsafe_allow_html=True)

    # ─── 1. 두더지 이동 (터치 못 하고 시간 초과된 경우 실패 기록) ─── ⭐
    if now - ss.last_mole_t > ss.mole_interval:
        if len(ss.lit_set) > 0: # 화면에 켜져 있던 두더지들이 있었는데 못 맞힌 경우
            for missed_id in list(ss.lit_set):
                ss.trial_counter += 1
                if ss.logger:
                    ss.logger.log(
                        trial_num=ss.trial_counter,
                        button_id=missed_id + 1,
                        reaction_ms=int(ss.mole_interval * 1000), # 최대 제한시간을 반응시간으로 기록
                        success=False,                             # 실패 기록
                        diff_level=ss.mode,
                        balance_lost=False
                    )
        spawn_moles()

    with cam_col:
        frame_rgb, result, hand_pts = read_frame_with_pose()
        h, w = frame_rgb.shape[:2]

        if result and result.pose_landmarks:
            lm = result.pose_landmarks.landmark
            def px(i):
                return (int(lm[i].x * w), int(lm[i].y * h))
            l_hip = px(23); r_hip = px(24)
            base_y = (l_hip[1] + r_hip[1]) // 2
            cv2.line(frame_rgb, (0, base_y), (w, base_y), (60, 100, 180), 1)
            ss.pose_status = "IN ZONE ✔"
        else:
            ss.pose_status = "카메라 확인"

        frame_rgb = draw_circles(frame_rgb, hand_pts)
        st.image(frame_rgb, channels="RGB", use_container_width=True)

    time.sleep(0.03)
    st.rerun()

# ─────────────────────────────────────────────────────────────
#  ⑤ 결과 화면
# ─────────────────────────────────────────────────────────────
def page_result():
    ss       = st.session_state
    color    = "#4F8EFF" if ss.mode == "normal" else "#E74C3C"
    mode_s   = "NORMAL" if ss.mode == "normal" else "HARD"
    badge    = "badge-normal" if ss.mode == "normal" else "badge-hard"
    last     = ss.session_rows[-1] if ss.session_rows else {}
    dur      = last.get("duration_s", 0)
    hits     = ss.score // 5
    g_text, g_class = grade(ss.score, ss.mode)

    # 로거에서 요약 데이터 가져오기 ⭐
    stats = ss.logger.summary() if ss.logger else {}

    st.markdown(f"""
    <div style='text-align:center; padding:30px 0 10px;'>
        <div style='font-size:50px;'>🏁</div>
        <div style='font-family:Share Tech Mono,monospace; font-size:30px; font-weight:bold; color:{color}; margin:4px 0;'>GAME OVER</div>
        <div style='color:#566573; font-size:14px;'>{ss.fail_reason}</div>
    </div>
    """, unsafe_allow_html=True)

    _, sc_col, _ = st.columns([1, 2, 1])
    with sc_col:
        # 로거 통계를 반영한 결과 카드 UI ⭐
        st.markdown(f"""
        <div class='card card-yellow' style='padding:24px 32px;'>
            <div style='font-size:14px; color:#566573; margin-bottom:8px;'>📊 피험자 [{ss.pid}] 실험 통계</div>
            <div style='display:grid; grid-template-columns: 1fr 1fr; gap:12px; font-family:Share Tech Mono,monospace;'>
                <div>총 타겟 수: <span style='color:white; font-weight:bold;'>{stats.get("total_trials", 0)}</span></div>
                <div>정확도(성공률): <span style='color:#2ECC71; font-weight:bold;'>{stats.get("accuracy", 0)}%</span></div>
                <div>평균 반응시간: <span style='color:#4F8EFF; font-weight:bold;'>{stats.get("mean_RT_ms", 0)} ms</span></div>
                <div>균형 실패 횟수: <span style='color:#E74C3C; font-weight:bold;'>{stats.get("balance_failures", 0)}</span></div>
            </div>
            <hr style='border-color:#22252E; margin:15px 0;'>
            <div style='text-align:center;'>
                <div class='label-sm'>최종 획득 점수</div>
                <div style='font-size:55px; font-weight:bold; color:#F1C40F; line-height:1.1;'>{ss.score} 점</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("↩  다시 하기", key="btn_retry", use_container_width=True):
                mode_bak   = ss.mode
                interval_b = ss.mole_interval
                num_lit_b  = ss.num_lit
                rows_bak   = ss.session_rows
                reset_to_login()
                st.session_state.mode          = mode_bak
                st.session_state.mole_interval = interval_b
                st.session_state.num_lit       = num_lit_b
                st.session_state.session_rows  = rows_bak
                st.session_state.phase         = "ready"
                st.rerun()
        with col_b:
            if st.button("🏠  모드 선택", key="btn_home", use_container_width=True):
                reset_to_login()
                st.rerun()

        st.markdown(f"""
        <div style='text-align:center; color:#566573; font-size:11px; font-family:Share Tech Mono,monospace; margin-top:12px;'>
            결과 저장: ~/balance_mole_{ss.session_id}.csv
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    div[data-testid="column"]:nth-child(1) .stButton>button { background:#4F8EFF; color:#000; width:100%; }
    div[data-testid="column"]:nth-child(2) .stButton>button { background:#1C1F2E; color:#ECF0F1; width:100%; }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  메인 라우터
# ─────────────────────────────────────────────────────────────
phase = st.session_state.phase

if phase == "login":
    page_login()
elif phase == "ready":
    page_ready()
elif phase == "countdown":
    page_countdown()
elif phase == "playing":
    page_playing()
elif phase == "result":
    page_result()
