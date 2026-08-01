"""
VELOCITY JAPANESE PODCAST GENERATOR
15-min bilingual Japanese/English podcast at A2 level with romaji
2 hosts: Hana & Kenji
"""
import os, sys, json, asyncio, subprocess, random, requests, re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter

load_dotenv()

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY") or "sk_K98O2j1UlpALX9TBAoAuEdqxL1hpB7zh"
AI_MODEL = os.getenv("AI_MODEL") or "openai"

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
FONTS_DIR = BASE_DIR / "fonts"

HOST1_VOICE = "ja-JP-NanamiNeural"
HOST2_VOICE = "ja-JP-KeitaNeural"

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

TOPICS = [
    "新しい国への旅行 - Traveling to a new country",
    "伝統的な食べ物 - Traditional food",
    "毎日の習慣 - Daily routine",
    "祝日とお祝い - Holidays and celebrations",
    "天気と季節 - Weather and seasons",
    "家族と友達 - Family and friends",
    "音楽と映画 - Music and movies",
    "スポーツと運動 - Sports and exercise",
    "理想の都市 - The ideal city",
    "言語を学ぶこと - Learning languages",
    "週末 - The weekend",
    "買い物と服 - Shopping and clothes",
    "公共交通機関 - Public transport",
    "レストランで - At the restaurant",
    "健康と幸福 - Health and wellness",
]

YELLOW = (247, 202, 0)
DARK_BG = (11, 14, 27)
WHITE = (255, 255, 255)
LIGHT_GRAY = (170, 180, 205)
DARK_LINE = (50, 55, 75)

def load_font(size, bold=False, italic=False):
    fonts_to_try = []
    if italic and bold:
        fonts_to_try.extend([
            "C:/Windows/Fonts/segoeuiz.ttf", "C:/Windows/Fonts/arialbi.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
            str(FONTS_DIR / "DejaVuSans-BoldOblique.ttf"),
        ])
    elif italic:
        fonts_to_try.extend([
            "C:/Windows/Fonts/segoeuii.ttf", "C:/Windows/Fonts/ariali.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            str(FONTS_DIR / "DejaVuSans-Oblique.ttf"),
        ])
    elif bold:
        fonts_to_try.extend([
            "C:/Windows/Fonts/Inter-Bold-slnt=0.ttf", "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            str(FONTS_DIR / "DejaVuSans-Bold.ttf"),
        ])
    else:
        fonts_to_try.extend([
            "C:/Windows/Fonts/Inter-Regular-slnt=0.ttf", "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            str(FONTS_DIR / "DejaVuSans.ttf"),
        ])

    for fp in fonts_to_try:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: continue
    return ImageFont.load_default()

def load_japanese_font(size, bold=False):
    """Load a font that supports Japanese characters (kana + kanji)."""
    if bold:
        candidates = [
            str(FONTS_DIR / "NotoSansJP-Bold.ttf"),
            "C:/Windows/Fonts/YuGothB.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        ]
    else:
        candidates = [
            str(FONTS_DIR / "NotoSansJP-Regular.ttf"),
            "C:/Windows/Fonts/YuGothM.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ]
    for fp in candidates:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: continue
    # fallback to the bundled DejaVu (will show boxes but not crash)
    return load_font(size, bold=bold)

def clean_text(text):
    text = re.sub(r'\b(mm+|um+|uh+|ah+|äh+)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def auto_highlight_japanese(text):
    if '**' in text:
        return text
    stopwords = {'は', 'が', 'を', 'に', 'で', 'と', 'も', 'の', 'です', 'ます', 'こと', 'これ', 'それ', '私', '僕', 'あなた'}
    words = text.split()
    candidates = []
    for idx, w in enumerate(words):
        clean_w = re.sub(r'[^\wÄÖÜäöüß]', '', w, flags=re.UNICODE)
        if clean_w.lower() not in stopwords and len(clean_w) >= 3:
            candidates.append((len(clean_w), idx, w, clean_w))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_idx = candidates[0][1]
        raw_w = words[best_idx]
        clean_w = candidates[0][3]
        highlighted = raw_w.replace(clean_w, f"**{clean_w}**")
        words[best_idx] = highlighted
        return " ".join(words)
    return text

def draw_microphone_icon(draw, center_x, center_y, radius=24):
    draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                 outline=YELLOW, width=3)
    w, h = 10, 18
    draw.rounded_rectangle([center_x - w//2, center_y - 12, center_x + w//2, center_y - 12 + h],
                           radius=4, fill=YELLOW)
    draw.arc([center_x - 10, center_y - 4, center_x + 10, center_y + 12],
             start=0, end=180, fill=YELLOW, width=3)
    draw.line([(center_x, center_y + 12), (center_x, center_y + 17)], fill=YELLOW, width=3)
    draw.line([(center_x - 7, center_y + 17), (center_x + 7, center_y + 17)], fill=YELLOW, width=3)

def draw_person_icon(draw, center_x, center_y):
    draw.ellipse([center_x - 6, center_y - 12, center_x + 6, center_y], fill=YELLOW)
    draw.chord([center_x - 12, center_y + 2, center_x + 12, center_y + 20],
               start=180, end=360, fill=YELLOW)

def draw_japanese_flag(img, draw, center_x, center_y, radius=22):
    flag_img = Image.new('RGBA', (radius*2, radius*2), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(flag_img)
    # Japanese flag: Black top (33%), Red middle (33%), Gold bottom (33%)
    h = radius * 2
    fdraw.rectangle([(0, 0), (radius*2, int(h * 0.33))], fill=(0, 0, 0, 255))
    fdraw.rectangle([(0, int(h * 0.33)), (radius*2, int(h * 0.66))], fill=(221, 0, 0, 255))
    fdraw.rectangle([(0, int(h * 0.66)), (radius*2, h)], fill=(255, 204, 0, 255))
    
    mask = Image.new('L', (radius*2, radius*2), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse([0, 0, radius*2, radius*2], fill=255)
    img.paste(flag_img, (center_x - radius, center_y - radius), mask)

def draw_headphones_icon(draw, center_x, center_y):
    draw.arc([center_x - 14, center_y - 14, center_x + 14, center_y + 6],
             start=180, end=360, fill=YELLOW, width=3)
    draw.rounded_rectangle([center_x - 16, center_y - 3, center_x - 10, center_y + 11], radius=2, fill=YELLOW)
    draw.rounded_rectangle([center_x + 10, center_y - 3, center_x + 16, center_y + 11], radius=2, fill=YELLOW)

def draw_rich_text_centered(draw, text, center_y, font, max_w=1550, line_height=90):
    text = auto_highlight_japanese(text)
    pattern = r'(\*\*.*?\*\*)'
    raw_parts = re.split(pattern, text)
    tokens = []
    for part in raw_parts:
        if part.startswith('**') and part.endswith('**'):
            tokens.append((part[2:-2], True))
        elif part:
            tokens.append((part, False))
            
    words_with_status = []
    for text_chunk, is_yellow in tokens:
        words = text_chunk.split(' ')
        for i, w in enumerate(words):
            if w:
                words_with_status.append((w, is_yellow))
            if i < len(words) - 1:
                words_with_status.append((' ', False))

    lines = []
    current_line = []
    current_line_width = 0

    for item in words_with_status:
        word, is_yellow = item
        w_bbox = draw.textbbox((0, 0), word, font=font)
        w_width = w_bbox[2] - w_bbox[0]

        if current_line_width + w_width <= max_w or not current_line:
            current_line.append((word, is_yellow, w_width))
            current_line_width += w_width
        else:
            if current_line and current_line[-1][0] == ' ':
                current_line_width -= current_line[-1][2]
                current_line.pop()
            lines.append((current_line, current_line_width))
            if word == ' ':
                current_line = []
                current_line_width = 0
            else:
                current_line = [(word, is_yellow, w_width)]
                current_line_width = w_width

    if current_line:
        if current_line[-1][0] == ' ':
            current_line_width -= current_line[-1][2]
            current_line.pop()
        lines.append((current_line, current_line_width))

    total_height = len(lines) * line_height
    start_y = center_y - total_height // 2

    for line_idx, (line_words, line_w) in enumerate(lines):
        start_x = (VIDEO_WIDTH - line_w) // 2
        curr_x = start_x
        curr_y = start_y + line_idx * line_height

        for word, is_yellow, w_w in line_words:
            color = YELLOW if is_yellow else WHITE
            draw.text((curr_x, curr_y), word, fill=color, font=font)
            curr_x += w_w

def draw_english_translation(draw, text, center_y, font, max_w=1350, line_height=52):
    words = text.split()
    lines = []
    current_line = []
    
    for w in words:
        test_line = ' '.join(current_line + [w])
        bb = draw.textbbox((0, 0), test_line, font=font)
        if bb[2] - bb[0] <= max_w:
            current_line.append(w)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [w]
    if current_line:
        lines.append(' '.join(current_line))
        
    total_h = len(lines) * line_height
    start_y = center_y - total_h // 2
    
    for idx, line in enumerate(lines):
        draw.text((VIDEO_WIDTH // 2, start_y + idx * line_height + line_height // 2),
                  line, fill=LIGHT_GRAY, font=font, anchor="mm")

def create_frame(turn, output_path, frame_num=0):
    img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), DARK_BG)
    draw = ImageDraw.Draw(img)

    glow = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([(-200, VIDEO_HEIGHT-600), (600, VIDEO_HEIGHT+200)], fill=(30, 20, 60, 40))
    gdraw.ellipse([(VIDEO_WIDTH-500, -200), (VIDEO_WIDTH+300, 600)], fill=(30, 20, 60, 40))
    img.paste(glow, (0, 0), glow)

    f_title_white = load_font(36, bold=True)
    f_title_sub = load_font(18, bold=False)
    f_title_sub_muted = load_font(15, bold=False)
    f_ep = load_font(22, bold=True)
    f_speaker = load_font(26, bold=True)
    f_hablando = load_font(24, bold=False)
    f_japanese = load_japanese_font(64, bold=True)
    f_english = load_font(42, bold=False, italic=True)
    f_footer = load_font(22, bold=False)

    # === TOP HEADER ===
    header_y = 68
    draw_microphone_icon(draw, center_x=70, center_y=header_y, radius=24)

    draw.text((110, header_y), "VELOCITY", fill=WHITE, font=f_title_white, anchor="lm")
    v_bbox = draw.textbbox((110, header_y), "VELOCITY", font=f_title_white, anchor="lm")
    
    draw.text((v_bbox[2] + 8, header_y), "JAPANESE", fill=YELLOW, font=f_title_white, anchor="lm")
    s_bbox = draw.textbbox((v_bbox[2] + 8, header_y), "JAPANESE", font=f_title_white, anchor="lm")

    draw.text((s_bbox[2] + 8, header_y), "PODCAST", fill=WHITE, font=f_title_white, anchor="lm")
    p_bbox = draw.textbbox((s_bbox[2] + 8, header_y), "PODCAST", font=f_title_white, anchor="lm")

    draw.line([(p_bbox[2] + 20, 48), (p_bbox[2] + 20, 88)], fill=DARK_LINE, width=2)

    sub_x = p_bbox[2] + 35
    draw.text((sub_x, header_y - 12), "Japanese Podcast", fill=WHITE, font=f_title_sub, anchor="lm")
    draw.text((sub_x, header_y + 12), "Learn Through Conversations", fill=LIGHT_GRAY, font=f_title_sub_muted, anchor="lm")

    ep_num = (frame_num // 150) + 1 if isinstance(frame_num, int) else 1
    ep_str = f"EP {ep_num:02d}"
    draw.rounded_rectangle([(1640, 46), (1750, 90)], radius=8, fill=YELLOW)
    draw.text((1695, header_y), ep_str, fill=DARK_BG, font=f_ep, anchor="mm")

    draw_japanese_flag(img, draw, center_x=1810, center_y=header_y, radius=22)

    draw.line([(0, 130), (VIDEO_WIDTH, 130)], fill=YELLOW, width=2)

    # === SPEAKER STATUS SECTION ===
    is_host1 = turn.get("speaker") == "Host1"
    speaker_name = "HANA" if is_host1 else "KENJI"
    pill_x, pill_y = 120, 210
    pill_w, pill_h = 220, 52

    draw.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
                           radius=26, outline=YELLOW, width=2)
    draw_person_icon(draw, center_x=pill_x + 36, center_y=pill_y + 26)
    draw.text((pill_x + 60, pill_y + 26), speaker_name, fill=YELLOW, font=f_speaker, anchor="lm")

    draw.text((pill_x + pill_w + 25, pill_y + 26), "hanashite imasu", fill=LIGHT_GRAY, font=f_hablando, anchor="lm")

    # === MAIN TEXT (auto-size, HARD max 3 lines) ===
    japanese_text = turn.get("japanese", turn.get("spanish", ""))
    chosen_font = None
    chosen_lh = 90
    final_lines = []
    for test_size in [64, 56, 48, 40, 34, 28, 24, 20]:
        test_font = load_japanese_font(test_size, bold=True)
        test_lh = int(test_size * 1.4)
        text_words = japanese_text.split()
        tmp_lines = []
        cur = []
        for w in text_words:
            test = ' '.join(cur + [w])
            bb = draw.textbbox((0, 0), test, font=test_font)
            if bb[2] - bb[0] <= 1550 or not cur:
                cur.append(w)
            else:
                tmp_lines.append(' '.join(cur))
                cur = [w]
        if cur: tmp_lines.append(' '.join(cur))
        if len(tmp_lines) <= 3:
            chosen_font = test_font
            chosen_lh = test_lh
            final_lines = tmp_lines
            break
    if chosen_font is None:
        chosen_font = load_japanese_font(20, bold=True)
        chosen_lh = int(20 * 1.4)
        text_words = japanese_text.split()
        tmp_lines = []
        cur = []
        for w in text_words:
            test = ' '.join(cur + [w])
            bb = draw.textbbox((0, 0), test, font=chosen_font)
            if bb[2] - bb[0] <= 1550 or not cur:
                cur.append(w)
            else:
                tmp_lines.append(' '.join(cur))
                cur = [w]
        if cur: tmp_lines.append(' '.join(cur))
        if len(tmp_lines) > 3:
            tmp_lines = tmp_lines[:3]
            if japanese_text:
                tmp_lines[-1] = tmp_lines[-1].rstrip() + "..."
        final_lines = tmp_lines
        japanese_text = " ".join(final_lines)
    draw_rich_text_centered(draw, japanese_text, center_y=390, font=chosen_font, max_w=1550, line_height=chosen_lh)

    # === ROMAJI (English transliteration) ===
    romaji_text = turn.get("romaji", "")
    if romaji_text:
        draw_english_translation(draw, romaji_text, center_y=570, font=f_english, max_w=1350, line_height=48)

    # === CENTER DIVIDER WITH DOT ===
    div_y = 660
    draw.line([(VIDEO_WIDTH//2 - 300, div_y), (VIDEO_WIDTH//2 + 300, div_y)], fill=YELLOW, width=2)
    draw.ellipse([(VIDEO_WIDTH//2 - 8, div_y - 8), (VIDEO_WIDTH//2 + 8, div_y + 8)], fill=YELLOW)

    # === ENGLISH TRANSLATION ===
    english_text = turn.get("english", "")
    draw_english_translation(draw, english_text, center_y=715, font=f_english, max_w=1350, line_height=52)

    # === BOTTOM FOOTER ===
    draw.line([(0, 975), (VIDEO_WIDTH, 975)], fill=YELLOW, width=2)

    footer_y = 1025
    draw_headphones_icon(draw, center_x=VIDEO_WIDTH//2 - 270, center_y=footer_y)
    draw.text((VIDEO_WIDTH//2 - 240, footer_y), "Learn Japanese Naturally", fill=WHITE, font=f_footer, anchor="lm")
    
    fn_bbox = draw.textbbox((VIDEO_WIDTH//2 - 240, footer_y), "Learn Japanese Naturally", font=f_footer, anchor="lm")
    draw.line([(fn_bbox[2] + 20, footer_y - 12), (fn_bbox[2] + 20, footer_y + 12)], fill=DARK_LINE, width=2)
    
    draw.text((fn_bbox[2] + 40, footer_y), "velocityjapanese.com", fill=WHITE, font=f_footer, anchor="lm")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=92)

def _fetch_turns_batch(topic, topic_es, topic_en, start_turn, batch_size=10):
    """Fetch one small batch of turns (reliable - avoids truncation)."""
    current_host = "Host2" if start_turn % 2 == 0 else "Host1"
    next_host = "Host1" if current_host == "Host2" else "Host2"
    host_role = "Kenji" if current_host == "Host2" else "Hana"

    intro_instruction = ""
    if start_turn == 0:
        intro_instruction = ("IMPORTANT: This is the FIRST batch. Keep the introduction SHORT - just 2 lines total "
                             "(one from Kenji/Host2, one from Hana/Host1), then immediately dive into the topic. "
                             "No long welcome speeches.\n")
    elif start_turn < 4:
        intro_instruction = "Continue naturally into the topic conversation. No new introductions.\n"

    prompt = f"""You are writing a Japanese/English learning podcast at A2 level with romaji.
Topic: {topic}

The dialogue so far is at turn {start_turn}. The current speaker is {host_role} ({current_host}).
Write the NEXT {batch_size} turns. Speakers STRICTLY alternate starting with {current_host}.

{intro_instruction}Each turn: 3-4 SHORT sentences (6-10 words each) with PERIODS for natural TTS pauses. 20-30 seconds spoken.
Simple present tense. A2 vocabulary. Natural Japanese. Include romaji (English transliteration) for every Japanese line. NO filler sounds.
IMPORTANT: Highlight exactly 1 key A2 target vocabulary word in each turn's Japanese text using double asterisks, for example: "Wir schauen in die **Zukunft**."

Return EXACTLY {batch_size} turns as a JSON array (no markdown). Each turn has "japanese" (Japanese text), "romaji" (English transliteration of the Japanese), and "english" (English translation):
[{{"speaker": "{current_host}", "japanese": "...", "romaji": "...", "english": "..."}},
 {{"speaker": "{next_host}", "japanese": "...", "romaji": "...", "english": "..."}}]"""

    for attempt in range(3):
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": "You write natural A2-level Japanese podcast scripts with VERY clear punctuation. Every sentence must have at least 2 commas for natural TTS pauses. Hana and Kenji strictly alternate. Highlight 1 key target word per turn in double asterisks like **Wort**. No filler sounds."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.9
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"}, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            script = None
            try:
                script = json.loads(content)
            except json.JSONDecodeError:
                recovered = []
                start = None
                depth = 0
                for ci, ch in enumerate(content):
                    if ch == '{':
                        if depth == 0:
                            start = ci
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0 and start is not None:
                            chunk = content[start:ci + 1]
                            try:
                                obj = json.loads(chunk)
                                if isinstance(obj, dict) and ("japanese" in obj or "english" in obj):
                                    recovered.append(obj)
                            except json.JSONDecodeError:
                                pass
                            start = None
                script = recovered
            if not isinstance(script, list):
                script = []

            valid = []
            for i, turn in enumerate(script):
                if not isinstance(turn, dict):
                    continue
                es = turn.get("japanese") or turn.get("spanish") or turn.get("text") or turn.get("content") or ""
                en = turn.get("english") or turn.get("translation") or ""
                romaji = turn.get("romaji") or turn.get("romanji") or turn.get("transliteration") or ""
                if not es:
                    continue
                valid.append({
                    "speaker": current_host if i % 2 == 0 else next_host,
                    "japanese": clean_text(es),
                    "romaji": clean_text(romaji) if romaji else "",
                    "english": clean_text(en) if en else "Translation unavailable"
                })
            if valid:
                return valid
        except Exception as e:
            print(f"  Batch attempt {attempt+1} failed: {e}")
    return None


def generate_script():
    topic = random.choice(TOPICS)
    topic_es = topic.split(" - ")[0]
    topic_en = topic.split(" - ")[1]

    TARGET = 150
    BATCH = 10
    all_turns = []
    consecutive_empty = 0
    import time as _time
    _deadline = _time.time() + 300  # hard cap: give up after 5 min of script generation

    while len(all_turns) < TARGET and consecutive_empty < 6 and _time.time() < _deadline:
        batch = _fetch_turns_batch(topic, topic_es, topic_en, len(all_turns), BATCH)
        if not batch:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                print("  API busy - waiting 10s before retrying...")
                _time.sleep(10)
            continue
        all_turns.extend(batch)
        consecutive_empty = 0
        print(f"  Script progress: {len(all_turns)}/{TARGET} turns")
        if len(all_turns) < TARGET:
            _time.sleep(2)

    all_turns = all_turns[:TARGET]

    if len(all_turns) < 30:
        print("  Too few turns from API, using fallback script")
        return _fallback_script(topic_es, topic_en), topic_es, topic_en

    # Short 2-line intro: Kenji (Host2) first, then Hana (Host1), then topic
    all_turns[0]["speaker"] = "Host2"
    all_turns[0]["japanese"] = f"こんにちは、健二です。Velocity Japanese へようこそ。今日は{topic_es}について話します。"
    all_turns[0]["romaji"] = f"Konnichiwa, Kenji desu. Velocity Japanese e yōkoso. Kyō wa {topic_es} ni tsuite hanashimasu."
    all_turns[0]["english"] = f"Hi, I'm Kenji. Welcome to Velocity Japanese Podcast. Today we talk about {topic_en}."
    if len(all_turns) > 1:
        all_turns[1]["speaker"] = "Host1"
        all_turns[1]["japanese"] = f"ありがとう、健二さん。今日のテーマはとても**面白い**です。始めましょう。"
        all_turns[1]["romaji"] = f"Arigatō, Kenji-san. Kyō no tēma wa totemo **omoshiroi** desu. Hajimemashō."
        all_turns[1]["english"] = f"Thanks, Kenji. Today's topic is very interesting. Let's start."

    print(f"  Script: {len(all_turns)} turns, topic: {topic_es}")
    return all_turns, topic_es, topic_en


def _fallback_script(topic_es, topic_en):
    turns = []
    for i in range(150):
        s = "Host2" if i % 2 == 0 else "Host1"
        if s == "Host2":
            turns.append({"speaker": s, "japanese": f"こんにちは、健二です。今日は{topic_es}について話します。", "romaji": f"Konnichiwa, Kenji desu. Kyou wa {topic_es} ni tsuite hanashimasu.", "english": f"Hi, I'm Kenji. Today we talk about {topic_en}."})
        else:
            turns.append({"speaker": s, "japanese": f"いいですね、健二さん。{topic_es}はとても**面白い**です。", "romaji": f"Ii desu ne, Kenji-san. {topic_es} wa totemo **omoshiroi** desu.", "english": f"Good idea, Kenji. {topic_en} is very interesting."})
    return turns


async def generate_audio(turns, target_dir=None):
    import edge_tts
    audio_files = []
    for i, turn in enumerate(turns):
        voice = HOST1_VOICE if turn["speaker"] == "Host1" else HOST2_VOICE
        audio_dir = Path(target_dir) if target_dir else OUTPUT_DIR
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, turn in enumerate(turns):
        voice = HOST1_VOICE if turn["speaker"] == "Host1" else HOST2_VOICE
        filename = audio_dir / f"audio_{i:03d}.mp3"
        spoken_text = re.sub(r'\*\*(.*?)\*\*', r'\1', turn.get("japanese", turn.get("spanish", "")))
        try:
            communicate = edge_tts.Communicate(spoken_text, voice)
            await communicate.save(str(filename))
            try:
                r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(filename)], capture_output=True, text=True)
                duration = float(r.stdout.strip()) if r.stdout else 3.0
            except:
                duration = 3.0
        except Exception as e:
            print(f"  Audio {i} failed: {e}")
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", str(filename)], capture_output=True)
            duration = 3.0
        audio_files.append({"path": str(filename), "duration": duration, "speaker": turn["speaker"]})
    return audio_files

def create_video(turns, audio_files, video_dir=None):
    if video_dir is None:
        video_dir = OUTPUT_DIR / f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_dir = Path(video_dir)
    video_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total_dur = 0

    for i, (turn, audio) in enumerate(zip(turns, audio_files)):
        img = video_dir / f"f_{i:04d}.png"
        create_frame(turn, str(img), i)
        clip = video_dir / f"c_{i:04d}.mp4"
        clips.append(clip)
        dur = audio["duration"]
        fade_start = max(0.0, dur - 0.3)
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", audio["path"],
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-preset", "medium",
            "-t", str(dur), "-af", f"afade=t=out:st={fade_start:.2f}:d=0.3",
            str(clip)
        ], check=True, capture_output=True)

        total_dur += audio["duration"]
        if (i + 1) % 25 == 0:
            print(f"  Frame {i+1}/{len(turns)}")

    concat = video_dir / "list.txt"
    with open(concat, "w") as f:
        for c in clips:
            f.write(f"file '{c.resolve().as_posix()}'\n")

    out = video_dir / "podcast_final.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-movflags", "+faststart", str(out)], check=True)

    for c in clips:
        c.unlink(missing_ok=True)
    for a in audio_files:
        try:
            Path(a["path"]).unlink(missing_ok=True)
        except Exception:
            pass
    if concat.exists():
        concat.unlink(missing_ok=True)

    return out, total_dur


async def main():
    print("=" * 60)
    print("  VELOCITY JAPANESE PODCAST")
    print("=" * 60)

    print("\n[1/4] Generating script (150 turns)...")
    turns, topic_es, topic_en = generate_script()

    video_dir = OUTPUT_DIR / f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_dir.mkdir(parents=True, exist_ok=True)

    with open(video_dir / "script.json", "w", encoding="utf-8") as f:
        json.dump({"topic": topic_es, "topic_en": topic_en, "turns": turns}, f, indent=2, ensure_ascii=False)

    print(f"\n[2/4] Generating audio ({len(turns)} turns)...")
    audio_files = await generate_audio(turns, video_dir)
    total_audio = sum(a["duration"] for a in audio_files)
    print(f"  Total audio: {total_audio/60:.1f} min")

    print(f"\n[3/4] Creating video...")
    video_path, duration = create_video(turns, audio_files, video_dir)

    print(f"\n[4/4] Saving...")
    first_frame = video_dir / "f_0000.png"
    thumbnail_path = video_dir / "thumbnail.jpg"
    try:
        from PIL import Image as _Img
        if first_frame.exists():
            _Img.open(str(first_frame)).convert("RGB").save(str(thumbnail_path), quality=92)
    except Exception as e:
        print(f"  Thumbnail warn: {e}")

    title = build_podcast_title(topic_es, topic_en)
    description = build_podcast_description(topic_es, topic_en, len(turns), round(duration / 60, 1))
    tags = ["Learn Japanese", "Japanese", "Japanese Podcast", "Learn Japanese Naturally",
            "Japanese for Beginners", "Bilingual", "Japanese Listening", "Japanese Conversation",
            topic_es, "Velocity Japanese"]

    meta_out = {
        "title": title,
        "description": description,
        "tags": tags,
        "category_english": topic_es,
        "language": "Japanese",
        "duration_minutes": round(duration / 60, 1),
        "turns_count": len(turns),
        "video_path": str(video_path),
        "thumbnail_path": str(thumbnail_path),
        "generated_at": datetime.now().isoformat(),
    }
    (OUTPUT_DIR).mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "latest_video.json", "w", encoding="utf-8") as f:
        json.dump(meta_out, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_DIR / "latest_upload_info.json", "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": description,
                   "category": topic_es, "turns_count": len(turns)}, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("  PODCAST COMPLETE!")
    print(f"  Topic: {topic_es}")
    print(f"  Duration: {duration/60:.1f} min ({len(turns)} turns)")
    print(f"  Video: {video_path.name}")
    print("=" * 60)


def build_podcast_title(topic_es, topic_en):
    titles = [
        f"Japanese Podcast: {topic_es} | 日本語を学ぶ",
        f"Learn Japanese: {topic_es} | Bilingual Podcast",
        f"{topic_es} | Japanese Conversation for Beginners",
        f"{topic_es} | Hana と Kenji と一緒に日本語を練習",
    ]
    return random.choice(titles)


def build_podcast_description(topic_es, topic_en, turns_count, duration_min):
    description = (
        f"🎙️ Velocity Japanese へようこそ。Yōkoso. Podcast!\n\n"
        f"このエピソードでは、Hana と Kenji がについて話します。Nihongo de: {topic_es} ({topic_en}).\n"
        f"A2レベルのリラックスしたバイリンガル会話で、日本語を自然に学べます。Romaji 付き。.\n\n"
        f"✨ WHAT'S INSIDE THIS EPISODE:\n"
        f"• {turns_count} 役立つ日本語のフレーズと表現\n"
        f"• 日常会話の実用的な語彙\n"
        f"• ネイティブの自然な発音\n"
        f"• 各行に英語訳とローマ字\n\n"
        f"📌 HOW TO USE THIS PODCAST:\n"
        f"1️⃣ 日本語の部分を聞いて理解してみてください\n"
        f"2️⃣ 英語の翻訳を確認してください\n"
        f"3️⃣ フレーズを声に出して繰り返してください\n"
        f"4️⃣ また明日聞いてください - 毎日簡単になります!\n\n"
        f"🔔 毎日新しいレッスンを購読してください.\n\n"
        f"📅 長さ: {duration_min} 分\n\n"
        f"#LearnJapanese #JapanesePodcast #Bilingual #LanguageLearning"
    )
    return description



if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('  Cancelled.')