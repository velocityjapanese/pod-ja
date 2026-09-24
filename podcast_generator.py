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

try:
    import pykakasi
    _kakasi_inst = pykakasi.kakasi()
except Exception:
    _kakasi_inst = None

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
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
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\b(mm+|um+|uh+|ah+|äh+)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _purify_japanese(text):
    """Remove stray Latin/English letters that leaked into the Japanese field.
    Keeps hiragana/katakana/kanji, Japanese punctuation, digits and the
    **bold** markers used for target-word highlighting. Converts any leftover
    Latin run (but not '**') into nothing so the Japanese line stays clean."""
    if not text:
        return text
    text = clean_text(text)
    text = text.replace('**', '\u0001')  # protect highlight markers
    text = re.sub(r'[A-Za-z\u00c0-\u024f]+', '', text)
    text = text.replace('\u0001', '**')
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ""
    return text

def to_accurate_romaji(japanese):
    """Accurate Japanese -> Hepburn Romaji converter.
    Uses pykakasi for full Kanji+Kana morphological transliteration with natural spacing.
    Falls back to kana mapping if pykakasi is unavailable."""
    if not japanese:
        return ""
    clean_ja = re.sub(r'\*\*(.*?)\*\*', r'\1', japanese)
    if _kakasi_inst is not None:
        try:
            res = _kakasi_inst.convert(clean_ja)
            words = [item['hepburn'] for item in res if item.get('hepburn')]
            romaji = ' '.join(words)
            romaji = re.sub(r'\s+([,!?.\u3001\u3002])', r'\1', romaji)
            romaji = romaji.replace('、', ', ').replace('。', '. ').replace('！', '! ').replace('？', '? ')
            romaji = re.sub(r'\s+', ' ', romaji).strip()
            sentences = re.split(r'([.!?]\s*)', romaji)
            cap_s = ''
            for s in sentences:
                if s and not s.isspace():
                    if not cap_s or cap_s.endswith('. ') or cap_s.endswith('! ') or cap_s.endswith('? '):
                        cap_s += s[0].upper() + s[1:] if len(s) > 1 else s.upper()
                    else:
                        cap_s += s
                else:
                    cap_s += s
            if re.search(r'[a-zA-Z]{2,}', cap_s):
                return cap_s.strip()
        except Exception as e:
            print(f"  pykakasi error: {e}")
    return _romanize_fallback(clean_ja)

def _romanize_fallback(japanese):
    """Lightweight kana->romaji converter used only when the AI omitted romaji.
    Handles hiragana/katakana digraphs, small-tsu gemination and basic long
    vowels. Kanji are kept as-is (they still render); punctuation is preserved.
    Never returns empty when there is any kana in the input."""
    if not japanese:
        return ""
    pairs = {
        'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
        'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
        'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
        'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
        'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
        'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
        'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
        'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
        'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
        'わ': 'wa', 'を': 'wo', 'ん': 'n', 'が': 'ga', 'ぎ': 'gi',
        'ぐ': 'gu', 'げ': 'ge', 'ご': 'go', 'ざ': 'za', 'じ': 'ji',
        'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo', 'だ': 'da', 'ぢ': 'ji',
        'づ': 'zu', 'で': 'de', 'ど': 'do', 'ば': 'ba', 'び': 'bi',
        'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo', 'ぱ': 'pa', 'ぴ': 'pi',
        'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
        'ゃ': 'ya', 'ゅ': 'yu', 'ょ': 'yo',
        'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
        'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
        'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
        'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
        'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
        'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
        'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
        'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
        'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
        'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n',
        'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
        'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
        'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
        'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
        'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
        'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo',
    }
    small_tsu = {'っ', 'ッ'}
    out = []
    i = 0
    n = len(japanese)
    while i < n:
        ch = japanese[i]
        if ch == 'ー':
            if out:
                out.append(out[-1])
            i += 1
            continue
        if ch in small_tsu:
            out.append('')
            i += 1
            continue
        if ch in pairs:
            r = pairs[ch]
            if out and out[-1] == '':
                out.pop()
                if r[0] in 'kgsztdhbp':
                    r = r[0] + r
                elif r in ('chi', 'tsu', 'shi'):
                    r = r[0] + r
            out.append(r)
            i += 1
            continue
        if ch in '、。，．！？':
            out.append(' ')
            i += 1
            continue
        out.append(ch)
        i += 1
    text = ''.join(out)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r' +([.,!?])', r'\1', text)
    return text


def sanitize_latin(text):
    """Convert leaked non-Latin characters to font-safe Latin equivalents so
    romaji/English never show tofu glyphs. Handles macrons, full-width forms
    and Japanese punctuation."""
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2026', '...').replace('\u2014', ' - ').replace('\u2013', ' - ')
    text = text.replace('\u3001', ', ').replace('\u3002', '.').replace('\u30fb', ' ')
    text = text.replace('\uff0c', ',').replace('\uff0e', '.').replace('\uff01', '!')
    text = text.replace('\uff1f', '?').replace('\uff20', '@')
    def norm_letter(m):
        ch = m.group(0)
        if ch == '\u0101': return 'a'
        if ch == '\u014d': return 'o'
        if ch == '\u016b': return 'u'
        if ch == '\u012b': return 'i'
        if ch == '\u0113': return 'e'
        if ch == '\u0100': return 'A'
        if ch == '\u014c': return 'O'
        if ch == '\u016a': return 'U'
        if ch == '\u012a': return 'I'
        if ch == '\u0112': return 'E'
        if ch == '\u00e9': return 'e'
        if ch == '\u00e8': return 'e'
        if ch == '\u00ea': return 'e'
        if ch == '\u00ef': return 'i'
        if ch == '\u00f1': return 'n'
        if ch == '\u00fc': return 'u'
        if ch == '\u00f6': return 'o'
        if ch == '\u00e4': return 'a'
        return ch
    text = re.sub(r'[\u00c0-\u024f\u0100-\u017f]', norm_letter, text)
    text = re.sub(r'[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef\u3000-\u303f]', ' ', text)
    # final safety net: map remaining symbols to ASCII, else drop (prevents any tofu glyph)
    text = text.replace('\u2192', ' -> ').replace('\u2190', ' <- ').replace('\u2194', ' -- ')
    text = text.replace('\u2022', '-').replace('\u25cf', '-').replace('\u2605', '*').replace('\u2606', '*')
    out = []
    for ch in text:
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            out.append(ch)
        elif o in (0x0A, 0x0D):
            out.append(' ')
        else:
            out.append(' ')
    text = ''.join(out)
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
    # Japanese flag: white background with red sun circle
    fdraw.rectangle([(0, 0), (radius*2, radius*2)], fill=(255, 255, 255, 255))
    fdraw.ellipse([(int(radius*0.6), int(radius*0.6)), (int(radius*1.4), int(radius*1.4))], fill=(188, 0, 45, 255))
    
    mask = Image.new('L', (radius*2, radius*2), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse([0, 0, radius*2, radius*2], fill=255)
    img.paste(flag_img, (center_x - radius, center_y - radius), mask)

def draw_headphones_icon(draw, center_x, center_y):
    draw.arc([center_x - 14, center_y - 14, center_x + 14, center_y + 6],
             start=180, end=360, fill=YELLOW, width=3)
    draw.rounded_rectangle([center_x - 16, center_y - 3, center_x - 10, center_y + 11], radius=2, fill=YELLOW)
    draw.rounded_rectangle([center_x + 10, center_y - 3, center_x + 16, center_y + 11], radius=2, fill=YELLOW)

def _cjk_tokens(text, font, draw):
    """Split text into drawable tokens (char-level for CJK, word-level for latin),
    each tagged with whether it belongs to a highlighted (**) segment."""
    pattern = r'(\*\*.*?\*\*)'
    raw_parts = re.split(pattern, text)
    tokens = []
    for part in raw_parts:
        if part.startswith('**') and part.endswith('**'):
            is_hl = True
            part = part[2:-2]
        elif part:
            is_hl = False
        else:
            continue
        if re.search(r'[\u3000-\u30ff\u4e00-\u9fff]', part):
            for ch in part:
                bb = draw.textbbox((0, 0), ch, font=font)
                tokens.append((ch, is_hl, bb[2] - bb[0]))
        else:
            for w in part.split(' '):
                if not w:
                    continue
                bb = draw.textbbox((0, 0), w, font=font)
                tokens.append((w, is_hl, bb[2] - bb[0]))
                tokens.append((' ', False, draw.textbbox((0, 0), ' ', font=font)[2]))
            if tokens and tokens[-1][0] == ' ':
                tokens.pop()
    return tokens

def _wrap_tokens(tokens, max_w):
    """Greedy wrap tokens into visual lines that each fit max_w."""
    lines = []
    current_line = []
    current_line_width = 0

    for word, is_hl, w_width in tokens:
        if current_line_width + w_width <= max_w:
            current_line.append((word, is_hl, w_width))
            current_line_width += w_width
        else:
            if current_line:
                if current_line[-1][0] == ' ':
                    current_line_width -= current_line[-1][2]
                    current_line.pop()
                lines.append((current_line, current_line_width))
            if word == ' ':
                current_line = []
                current_line_width = 0
            else:
                current_line = [(word, is_hl, w_width)]
                current_line_width = w_width

    if current_line:
        if current_line[-1][0] == ' ':
            current_line_width -= current_line[-1][2]
            current_line.pop()
        lines.append((current_line, current_line_width))
    return lines

def draw_rich_text_centered(draw, text, center_y, font, max_w=1550, line_height=90):
    text = auto_highlight_japanese(text)
    tokens = _cjk_tokens(text, font, draw)
    lines = _wrap_tokens(tokens, max_w)

    total_height = len(lines) * line_height
    start_y = center_y - total_height // 2
    ink_min_top = None
    ink_max = None

    for line_idx, (line_words, line_w) in enumerate(lines):
        start_x = (VIDEO_WIDTH - line_w) // 2
        curr_x = start_x
        curr_y = start_y + line_idx * line_height

        for word, is_yellow, w_w in line_words:
            color = YELLOW if is_yellow else WHITE
            draw.text((curr_x, curr_y), word, fill=color, font=font)
            bb = draw.textbbox((curr_x, curr_y), word, font=font)
            ink_min_top = min(ink_min_top, bb[1]) if ink_min_top is not None else bb[1]
            ink_max = max(ink_max, bb[3]) if ink_max is not None else bb[3]
            curr_x += w_w

    if ink_min_top is None:
        ink_min_top = start_y
        ink_max = start_y + total_height
    return ink_min_top, ink_max

def _ro_ink_height(font, lines, max_w=1350):
    """Return the measured ink height of the given (already-wrapped) latin lines."""
    from PIL import Image, ImageDraw
    if not lines:
        return 0
    tmp = Image.new('RGB', (max_w, 200), (0, 0, 0))
    td = ImageDraw.Draw(tmp)
    probe = lines[0]
    bb = td.textbbox((0, 0), probe, font=font)
    h = bb[3] - bb[1]
    if len(lines) > 1:
        h += (len(lines) - 1) * int(font.size * 1.3)
    return h

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

    ink_min_top = None
    ink_max = None
    for idx, line in enumerate(lines):
        lx = VIDEO_WIDTH // 2
        ly = start_y + idx * line_height + line_height // 2
        draw.text((lx, ly), line, fill=LIGHT_GRAY, font=font, anchor="mm")
        bb = draw.textbbox((lx, ly), line, font=font, anchor="mm")
        ink_min_top = bb[1] if ink_min_top is None else min(ink_min_top, bb[1])
        ink_max = bb[3] if ink_max is None else max(ink_max, bb[3])
    if ink_min_top is None:
        ink_min_top = start_y
        ink_max = start_y + total_h
    return ink_min_top, ink_max

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

    # === MAIN TEXT ZONE: Japanese + Romaji, must BOTH fit above the center divider ===
    ZONE_TOP = 300
    DIV_Y = 615
    ZONE_BOTTOM = DIV_Y - 30
    ZONE_H = ZONE_BOTTOM - ZONE_TOP
    japanese_text = turn.get("japanese", turn.get("spanish", ""))
    romaji_text = sanitize_latin(turn.get("romaji", ""))
    if not re.search(r'[a-zA-Z]{2,}', romaji_text):
        romaji_text = to_accurate_romaji(japanese_text)
    if not re.search(r'[a-zA-Z]{2,}', romaji_text):
        romaji_text = sanitize_latin(turn.get("english", ""))

    def _wrap(text, font, max_w):
        tokens = _cjk_tokens(text, font, draw)
        wrapped = _wrap_tokens(tokens, max_w)
        return [' '.join(w for w, hl, ww in line).strip() for line, wd in wrapped]

    # 1) choose the largest Japanese font that wraps into <= 3 lines
    ja_font = None
    ja_size = 64
    final_lines = []
    for test_size in [64, 56, 48, 40, 34, 28, 24, 20]:
        tf = load_japanese_font(test_size, bold=True)
        tl = _wrap(japanese_text, tf, 1550)
        if len(tl) <= 3:
            ja_font, ja_size, final_lines = tf, test_size, tl
            break
    if ja_font is None:
        ja_font, ja_size = load_japanese_font(20, bold=True), 20
        all_lines = _wrap(japanese_text, ja_font, 1550)
        final_lines = all_lines[:3]
        if len(all_lines) > 3 and japanese_text:
            final_lines[-1] = final_lines[-1].rstrip() + "..."
    n_ja = len(final_lines)

    # 2) wrap romaji at the starting italic size
    ro_size = 40
    ro_font = load_font(ro_size, bold=False, italic=True)
    ro_lines = _wrap(romaji_text, ro_font, 1350) if romaji_text else []
    n_ro = len(ro_lines)

    JA_RO_GAP = 14
    SAFE_BOTTOM = ZONE_BOTTOM - 6

    def _measure_block():
        """Render ja+ro to a temp canvas and return (ja_center, ro_center, ink_bottom).
        Mirrors the real draw path so measured ink is exactly what appears."""
        tmp = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), DARK_BG)
        td = ImageDraw.Draw(tmp)
        ja_lh_ = int(ja_size * 1.4)
        ja_center = ZONE_TOP + len(final_lines) * ja_lh_ // 2
        _, ja_ib = draw_rich_text_centered(td, " ".join(final_lines),
                                           center_y=ja_center, font=ja_font,
                                           max_w=1550, line_height=ja_lh_)
        if not n_ro:
            return ja_center, None, ja_ib
        ih = _ro_ink_height(ro_font, ro_lines)
        target_top = ja_ib + JA_RO_GAP
        ly0 = target_top + ih / 2
        ro_center = ly0 - ro_lh // 2 + (n_ro * ro_lh) // 2
        _, ro_ib = draw_english_translation(td, " ".join(ro_lines), center_y=ro_center,
                                            font=ro_font, max_w=1350, line_height=ro_lh)
        return ja_center, ro_center, ro_ib

    # 3) dynamically shrink BOTH fonts until the MEASURED ink block stays
    #    clear of the center divider (real ink, not just estimated line-h).
    ja_lh = int(ja_size * 1.4)
    ro_lh = int(ro_size * 1.3)
    while True:
        ja_center, ro_center, ink_bottom = _measure_block()
        if ink_bottom <= SAFE_BOTTOM or ja_size <= 20:
            break
        ja_size = max(20, ja_size - 2)
        ro_size = max(18, ro_size - 1)
        ja_font = load_japanese_font(ja_size, bold=True)
        ro_font = load_font(ro_size, bold=False, italic=True)
        final_lines = _wrap(japanese_text, ja_font, 1550)
        n_ja = len(final_lines)
        ro_lines = _wrap(romaji_text, ro_font, 1350) if romaji_text else []
        n_ro = len(ro_lines)
        ja_lh = int(ja_size * 1.4)
        ro_lh = int(ro_size * 1.3)

    ja_center, ro_center, _ = _measure_block()
    draw_rich_text_centered(draw, " ".join(final_lines), center_y=ja_center,
                            font=ja_font, max_w=1550, line_height=ja_lh)
    if n_ro and ro_center is not None:
        draw_english_translation(draw, " ".join(ro_lines), center_y=ro_center,
                                 font=ro_font, max_w=1350, line_height=ro_lh)

    # === CENTER DIVIDER WITH DOT ===
    div_y = 615
    draw.line([(VIDEO_WIDTH//2 - 300, div_y), (VIDEO_WIDTH//2 + 300, div_y)], fill=YELLOW, width=2)
    draw.ellipse([(VIDEO_WIDTH//2 - 8, div_y - 8), (VIDEO_WIDTH//2 + 8, div_y + 8)], fill=YELLOW)

    # === ENGLISH TRANSLATION (ITALIC, WRAPPED) ===
    english_text = sanitize_latin(turn.get("english", ""))
    draw_english_translation(draw, english_text, center_y=715, font=f_english, max_w=1350, line_height=48)

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


def parse_turns_json(content, target_key="japanese"):
    """Robustly parse JSON array of turns from LLM output, handling unescaped control chars, code fences, and partial json."""
    clean = content.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif "```" in clean:
        clean = clean.split("```")[1].split("```")[0].strip()

    try:
        obj = json.loads(clean, strict=False)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    fixed = re.sub(r'(?<!\\)\n', r'\\n', clean)
    try:
        obj = json.loads(fixed, strict=False)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    recovered = []
    start = None
    depth = 0
    for ci, ch in enumerate(clean):
        if ch == '{':
            if depth == 0:
                start = ci
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                chunk = clean[start:ci + 1]
                try:
                    t = json.loads(chunk, strict=False)
                    if isinstance(t, dict):
                        recovered.append(t)
                except Exception:
                    try:
                        chunk_fixed = re.sub(r'(?<!\\)\n', r'\\n', chunk)
                        t = json.loads(chunk_fixed, strict=False)
                        if isinstance(t, dict):
                            recovered.append(t)
                    except Exception:
                        pass
                start = None
    if recovered:
        return recovered

    regex = re.compile(
        r'\{\s*"speaker"\s*:\s*"(?P<speaker>[^"]+)"\s*,\s*'
        r'(?:"(?:' + target_key + r'|text|content|spanish)"\s*:\s*"(?P<tgt>.*?)"\s*,\s*)?'
        r'(?:"(?:romaji|translit|transliteration)"\s*:\s*"(?P<ro>.*?)"\s*,\s*)?'
        r'(?:"english"\s*:\s*"(?P<en>.*?)"\s*)?'
        r'\}', re.DOTALL
    )
    for m in regex.finditer(clean):
        spk = m.group("speaker") or "Host1"
        tgt = m.group("tgt") or ""
        ro = m.group("ro") or ""
        en = m.group("en") or ""
        if tgt:
            recovered.append({"speaker": spk, target_key: tgt, "romaji": ro, "english": en})

    return recovered

def _fetch_turns_batch(topic, topic_es, topic_en, start_turn, batch_size=10):
    """Fetch one small batch of turns with multi-model fallback and robust parsing."""
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
Simple present tense. A2 vocabulary. Natural Japanese. Include romaji (English transliteration in Latin letters) for every Japanese line. NO filler sounds.
IMPORTANT: The "japanese" field MUST be written 100% in Japanese characters (hiragana, katakana, kanji).
IMPORTANT: The "romaji" field MUST be written 100% in Latin letters (Hepburn romanization).
IMPORTANT: Highlight exactly 1 key A2 target vocabulary word in each turn's Japanese text using double asterisks, for example: "私たちは**未来**を見ます。"
IMPORTANT: Format as a single compact JSON array without unescaped line breaks inside string values.

Return EXACTLY {batch_size} turns as a JSON array (no markdown):
[{{"speaker": "{current_host}", "japanese": "...", "romaji": "...", "english": "..."}},
 {{"speaker": "{next_host}", "japanese": "...", "romaji": "...", "english": "..."}}]"""

    candidate_models = [AI_MODEL, "openai", "mistral", "qwen"]
    models_to_try = []
    for mod in candidate_models:
        if mod and mod not in models_to_try:
            models_to_try.append(mod)

    for attempt, model_name in enumerate(models_to_try):
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You write natural A2-level Japanese podcast scripts with VERY clear punctuation. Every sentence must have at least 2 commas for natural TTS pauses. Hana and Kenji strictly alternate. Highlight 1 key target word per turn in double asterisks like **tango**. No filler sounds. CRITICAL: the japanese field must contain ONLY Japanese script (hiragana/katakana/kanji). The romaji field must contain ONLY Latin letters Hepburn transliteration. English belongs only in the english field. Output single compact JSON array without unescaped newlines inside strings."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"} if POLLINATIONS_API_KEY else {}, timeout=45)
            if resp.status_code != 200:
                print(f"  Batch attempt {attempt+1} ({model_name}) returned HTTP {resp.status_code}", flush=True)
                continue
            content = resp.json()["choices"][0]["message"]["content"].strip()
            script = parse_turns_json(content, "japanese")
            valid = []
            for i, turn in enumerate(script):
                if not isinstance(turn, dict):
                    continue
                ja = turn.get("japanese") or turn.get("text") or turn.get("content") or turn.get("spanish") or ""
                en = turn.get("english") or turn.get("translation") or ""
                ro = sanitize_latin(turn.get("romaji") or turn.get("translit") or turn.get("romanji") or "")
                if not ja:
                    continue
                if not re.search(r'[a-zA-Z]{2,}', ro):
                    ro = to_accurate_romaji(ja)
                valid.append({
                    "speaker": current_host if i % 2 == 0 else next_host,
                    "japanese": clean_text(ja),
                    "romaji": ro,
                    "english": clean_text(en) if en else "Translation unavailable"
                })
            if len(valid) >= 4:
                return valid
            else:
                print(f"  Batch attempt {attempt+1} ({model_name}) parsed only {len(valid)} turns, trying next model...", flush=True)
        except Exception as e:
            print(f"  Batch attempt {attempt+1} ({model_name}) failed: {e}", flush=True)
            import time
            time.sleep(1)
    return None


def _generate_topic():
    """Have the AI invent a brand-new random topic (unlimited variety).
    Returns '<topic - English>' or None on failure (caller falls back to TOPICS)."""
    seed = random.randint(100000, 999999)
    candidate_models = [AI_MODEL, "openai", "mistral"]
    for m in candidate_models:
        if not m:
            continue
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": m,
                "messages": [
                    {"role": "system", "content": "You invent fresh, interesting, everyday topics for a Japanese/English A2 learning podcast. Always pick something new and varied from all areas of daily life, as a SHORT noun phrase (2-5 words), NOT a full sentence."},
                    {"role": "user", "content": f"Create EXACTLY ONE brand-new topic (uniqueness seed {seed}) for a Japanese/English A2 podcast. Return ONLY one line in this exact format: <topic in Japanese> - <topic in English>. The first part must be a short noun phrase in Japanese. No numbering, no bullets, no extra text."}
                ],
                "temperature": 1.1,
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"} if POLLINATIONS_API_KEY else {}, timeout=45)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip().strip('"').strip()
                if content and " - " in content:
                    return content
        except Exception as e:
            print(f"  Topic gen ({m}) failed: {e}", flush=True)
    return None


def _fallback_script(topic_es, topic_en, target=150):
    """Generate 150 unique, educational, progressive dialogue turns in Japanese with romaji covering diverse conversation phases."""
    topic_ro = to_accurate_romaji(topic_es)
    phases = [
        # Phase 1: Greetings & Introduction
        [
            ("Host2", f"皆さん、こんにちは。健二です。Velocity Japaneseへようこそ！今日は**{topic_es}**について話します。",
                      f"Hello everyone. I'm Kenji. Welcome to Velocity Japanese! Today we talk about {topic_en}."),
            ("Host1", f"こんにちは、健二さん。リスナーの皆さん、ようこそ！このテーマは日本語学習にとって、とても**大切**ですね。",
                      f"Hello Kenji. Welcome listeners! This topic is very important for learning Japanese."),
            ("Host2", f"その通りです、花さん。毎日の中でよく見かけますが、どう話せばいいか迷う人も多いです。",
                      f"That's right, Hana. We often see it in daily life, but many people hesitate on how to talk about it."),
            ("Host1", f"そうですね。だから今日は**簡単**な文と分かりやすい言葉を使って、楽しく進めましょう。",
                      f"Indeed. So today let's use simple sentences and clear words to proceed enjoyably."),
            ("Host2", f"素晴らしい！最初の質問ですが、花さんにとって**{topic_es}**はどんな存在ですか？",
                      f"Wonderful! For the first question, what kind of presence is {topic_en} for you, Hana?"),
            ("Host1", f"私にとっては、毎日の生活を明るくしてくれる大切な**一部**ですね。",
                      f"For me, it's an important part of life that brightens each day."),
            ("Host2", f"私も全く同感です。意識して楽しむことで、一日がもっと**豊か**になります。",
                      f"I completely agree. By mindfully enjoying it, the day becomes much richer."),
            ("Host1", f"はい、必要な単語をしっかり覚えると、自然な**会話**がどんどんできるようになります。",
                      f"Yes, once you remember the necessary words, natural conversation becomes easier and easier."),
            ("Host2", f"リスナーの皆さんも、今日のキーワードをぜひ声に出して**練習**してみてください。",
                      f"Listeners, please also try practicing today's keywords out loud."),
            ("Host1", f"いいですね！では、**{topic_es}**についての具体的なお話に入っていきましょう。",
                      f"Sounds good! Let's get into concrete details about {topic_en}.")
        ],
        # Phase 2: Morning routine & habits
        [
            ("Host2", f"花さんは、普段の朝に**{topic_es}**のことを考えることがありますか？",
                      f"Hana, on a normal morning do you ever think about {topic_en}?"),
            ("Host1", f"はい、朝早く起きると気分が落ち着いて、いいアイデアが**生まれます**。",
                      f"Yes, waking up early calms my mind and brings good ideas."),
            ("Host2", f"朝の静かな時間は特別ですね。焦らずに自分の**時間**を過ごすことができます。",
                      f"The quiet morning time is special. You can spend your own time without rushing."),
            ("Host1", f"慌ただしい生活は疲れますからね。朝の良い**習慣**が一日を快適にします。",
                      f"Rushed life is tiring. A good morning habit makes the whole day comfortable."),
            ("Host2", f"夕方や仕事の後に**{topic_es}**を楽しむ人もたくさんいますね。",
                      f"There are also many people who enjoy {topic_en} in the evening or after work."),
            ("Host1", f"人それぞれのライフスタイルに合わせて、無理のない**バランス**を見つけることが大切です。",
                      f"Matching each person's lifestyle, finding a reasonable balance is what matters."),
            ("Host2", f"本当にそうですね。自分のペースを知ることが、心地よい**暮らし**につながります。",
                      f"Truly so. Knowing your own pace leads to a comfortable living."),
            ("Host1", f"そして日本語学習でも、毎日の少しずつの積み重ねが確かな**力**になります。",
                      f"And in Japanese learning too, a little daily accumulation becomes dependable ability."),
            ("Host2", f"その通りです。毎日十分の練習は、週末だけの二時間よりもずっと**効果的**です。",
                      f"That's right. Ten minutes of practice every day is far more effective than two hours on the weekend."),
            ("Host1", f"では次に、日本の街の中で見かける**{topic_es}**について話してみましょう。",
                      f"Next, let's talk about {topic_en} seen in Japanese towns.")
        ],
        # Phase 3: In the city & culture
        [
            ("Host2", f"日本の街を歩くと、**{topic_es}**に関するお店や案内をよく見かけますね。",
                      f"Walking through Japanese towns, we often see shops and signs related to {topic_en}."),
            ("Host1", f"はい、駅の近くや商店街で、たくさんの人が**興味**を持って集まっています。",
                      f"Yes, near train stations and shopping arcades, many people gather with interest."),
            ("Host2", f"友達と一緒にそういう場所を訪ねるのは、とても楽しい**時間**です。",
                      f"Visiting such places with friends is a very fun time."),
            ("Host1", f"誰かと気持ちを共有できると、心も自然と**温かく**なりますね。",
                      f"When you can share feelings with someone, your heart naturally becomes warm."),
            ("Host2", f"日本人が**{topic_es}**について話すとき、どんな言葉をよく使いますか？",
                      f"When Japanese people talk about {topic_en}, what words do they often use?"),
            ("Host1", f"『便利』や『丁寧』、そして『素晴らしい』という言葉で、その**品質**を褒めます。",
                      f"With words like 'convenient', 'polite', and 'wonderful', they praise its quality."),
            ("Host2", f"『品質』へのこだわりは、日本のものづくりやサービスの大きな**特徴**ですね。",
                      f"Attention to 'quality' is a major feature of Japanese craftsmanship and service."),
            ("Host1", f"少し手間がかかっても、丁寧なものを選ぶと長く安心して**使えます**。",
                      f"Even if it takes extra care, choosing careful craftsmanship allows long and reassuring use."),
            ("Host2", f"日本を旅行する方へのアドバイスですが、地元の人に気軽に**質問**してみてください。",
                      f"Here's advice for travelers in Japan: feel free to ask local people questions."),
            ("Host1", f"地元の方は親切に、**{topic_es}**が楽しめるおすすめの場所を教えてくれますよ。",
                      f"Local residents will kindly tell you recommended spots to enjoy {topic_en}.")
        ],
        # Phase 4: Advice for beginners & learning mindset
        [
            ("Host2", f"リスナーの方から質問です。**{topic_es}**についての日本語を理解するのは難しいですか？",
                      f"Question from a listener: is it difficult to understand Japanese about {topic_en}?"),
            ("Host1", f"最初は難しく感じるかもしれませんが、少しずつ慣れるととても**明確**になります。",
                      f"At first it may feel difficult, but as you gradually get used to it, it becomes very clear."),
            ("Host2", f"初心者が最初にしてしまいがちな**間違い**は何でしょうか？",
                      f"What mistake do beginners tend to make at first?"),
            ("Host1", f"完璧に話そうとしすぎて、話すのが怖くなってしまうのが一番の**壁**ですね。",
                      f"Trying too hard to speak perfectly and becoming scared to speak is the biggest obstacle."),
            ("Host2", f"間違えるのは当たり前ですし、むしろ失敗から学ぶことの方が**多い**です。",
                      f"Making mistakes is natural, and in fact we learn more from mistakes."),
            ("Host1", f"その通りです。実際の会話では、伝えたいという**気持ち**が一番相手に届きます。",
                      f"That's right. In real conversation, the wish to communicate reaches the partner best."),
            ("Host2", f"外国の方が一生懸命日本語で話してくれると、日本人はとても**嬉しい**ものです。",
                      f"When foreigners try hard to speak Japanese, Japanese people feel very happy."),
            ("Host1", f"温かい笑顔で答えてくれるので、自信を持ってどんどん**挑戦**してください。",
                      f"They will answer with a warm smile, so please challenge yourself with confidence."),
            ("Host2", f"ですから、機会があればぜひ**{topic_es}**の話題を出してみてくださいね。",
                      f"Therefore, if you have an opportunity, please bring up {topic_en} as a topic."),
            ("Host1", f"このエピソードで覚えたフレーズを、さっそく使って**みましょう**。",
                      f"Let's immediately try using the phrases learned in this episode.")
        ],
        # Phase 5: Japanese traditions & lifestyle
        [
            ("Host2", f"花さん、地域によって**{topic_es}**の受け止め方に違いはありますか？",
                      f"Hana, are there differences in how {topic_en} is perceived across regions?"),
            ("Host1", f"東京と京都や地方では雰囲気が違いますが、大切にする心はどこでも**同じ**です。",
                      f"Atmosphere differs between Tokyo, Kyoto and regional towns, but the caring spirit is the same everywhere."),
            ("Host2", f"日本全国の豊かな風土や歴史が、様々な**魅力**を生み出していますね。",
                      f"The rich climate and history across all Japan generate various charms."),
            ("Host1", f"四季折々の変化を感じながら暮らすことが、日本文化の素敵な**伝統**です。",
                      f"Living while feeling the seasonal changes is a wonderful tradition of Japanese culture."),
            ("Host2", f"海外から来る方々も、この静けさと細やかな心遣いに深く**感動**されます。",
                      f"Visitors from overseas are also deeply moved by this quietness and detailed thoughtfulness."),
            ("Host1", f"人と人との繋がりや、周りへの思いやりが生活の**基本**にあるからですね。",
                      f"Because human connection and caring for others form the foundation of life."),
            ("Host2", f"そして**{topic_es}**も、そんな日本の思いやりの文化と深く結びついています。",
                      f"And {topic_en} is also deeply connected with such Japanese culture of consideration."),
            ("Host1", f"ただの言葉ではなく、お互いの心を結ぶ温かい**体験**になります。",
                      f"Rather than just words, it becomes a warm experience connecting hearts."),
            ("Host2", f"良い思い出を誰かと分かち合うと、喜びはさらに**大きく**広がりますね。",
                      f"When sharing good memories with someone, joy expands even more."),
            ("Host1", f"本当にそうですね。ささやかな日常の中にこそ、最高の**幸せ**があります。",
                      f"Truly so. In modest daily life itself lies the greatest happiness.")
        ],
        # Phase 6: Practical learning tips
        [
            ("Host2", f"ここで、リスナーの皆さんに**{topic_es}**を上手に学ぶためのコツを三つ紹介しましょう。",
                      f"Here, let's introduce three tips to listeners for learning {topic_en} skillfully."),
            ("Host1", f"一つ目は、小さなノートを用意して、新しく知った文を毎日二つ**書く**ことです。",
                      f"The first is preparing a small notebook and writing down two newly learned sentences every day."),
            ("Host2", f"手で文字を書くと、記憶に残りやすくなってとても**効果的**ですね。",
                      f"Writing characters by hand makes them easier to remember and is very effective."),
            ("Host1", f"二つ目は、通勤や散歩のときにイヤホンで日本語の音声を**聞く**ことです。",
                      f"The second is listening to Japanese audio on earphones while commuting or walking."),
            ("Host2", f"耳が日本語のイントネーションやリズムに自然と**慣れて**いきます。",
                      f"Your ears naturally get accustomed to Japanese intonation and rhythm."),
            ("Host1", f"そして三つ目は、単語をバラバラでなく、文全体の**形**で覚えることです。",
                      f"And the third is remembering words in the form of entire sentences, not separately."),
            ("Host2", f"そうすれば、実際の会話のときに自然と言葉が口から**出てきます**。",
                      f"That way, during actual conversation words will come out naturally from your mouth."),
            ("Host1", f"このVelocity Japaneseのポッドキャストも、その方法で**作られています**。",
                      f"This Velocity Japanese podcast is also created with that method."),
            ("Host2", f"コメント欄でも、上達を感じているという嬉しい声をたくさん**いただきます**。",
                      f"In the comment section too, we receive many happy voices saying they feel improvement."),
            ("Host1", f"皆さんからの応援が、私たちの毎日の大きな**励み**になっています。",
                      f"Support from everyone is our great daily encouragement.")
        ],
        # Phase 7: Real-world conversation roleplay
        [
            ("Host2", f"では短いロールプレイをしてみましょう。お店で**{topic_es}**について尋ねる場面です。",
                      f"Now let's do a short roleplay. It's a scene asking about {topic_en} at a shop."),
            ("Host1", f"楽しそうですね！『すみません、初心者にはどれがおすすめか**教えて**いただけますか？』",
                      f"Sounds fun! 'Excuse me, could you teach me which one is recommended for a beginner?'"),
            ("Host2", f"『いらっしゃいませ！初めての方には、こちらの使いやすい定番のものが**人気**ですよ。』",
                      f"'Welcome! For first-timers, this easy-to-use classic item is popular.'"),
            ("Host1", f"『ありがとうございます！上手に慣れるまで、どれくらい時間が**かかります**か？』",
                      f"'Thank you! About how long does it take until getting skillfully used to it?'"),
            ("Host2", f"『毎日少しずつ試していただければ、一週間ほどで十分に**慣れます**よ。』",
                      f"'If you try a little each day, you will be well accustomed in about a week.'"),
            ("Host1", f"『安心しました！では、今日からさっそく使って**みます**。』",
                      f"'I feel relieved! Then I will try using it right away from today.'"),
            ("Host2", f"こういう丁寧で実用的なやり取りは、日本全国のどこでも**使えます**ね。",
                      f"Polite and practical interactions like this can be used anywhere across Japan."),
            ("Host1", f"『教えていただけますか』という表現は、とても礼儀正しくて好印象を**与えます**。",
                      f"The expression 'could you teach me' is very courteous and gives a good impression."),
            ("Host2", f"丁寧な言葉遣いは、相手との関係をぐっと良くして**くれます**。",
                      f"Polite phrasing significantly improves relationships with conversation partners."),
            ("Host1", f"皆さんも日本へ旅行した際には、ぜひ使って**みてください**。",
                      f"Everyone, when traveling to Japan, please try using it.")
        ],
        # Phase 8: Personal reflections & confidence
        [
            ("Host2", f"花さんの周りの友人たちは、**{topic_es}**についてどんな反応をしますか？",
                      f"Hana, how do your friends react when talking about {topic_en}?"),
            ("Host1", f"最初は不思議そうにしていましたが、実際に体験するとみんな**納得**していました。",
                      f"At first they seemed curious, but upon experiencing it they all understood."),
            ("Host2", f"新しいことに触れるときの少しの緊張は、誰にでもある自然な**気持ち**です。",
                      f"A little nervousness when encountering something new is a natural feeling anyone has."),
            ("Host1", f"でも一歩を踏み出すと、不安が消えて大きな**自信**へと変わっていきます。",
                      f"But taking a step forward turns anxiety into great confidence."),
            ("Host2", f"声に出して話す回数が増えるほど、日本語の会話力はぐんぐん**伸びます**。",
                      f"The more times you speak out loud, the more your Japanese speaking ability grows."),
            ("Host1", f"少ない語彙であっても、相手を思う気持ちがあれば十分に心を通わせることが**できます**。",
                      f"Even with small vocabulary, if you have caring feelings you can fully communicate."),
            ("Host2", f"世界中のリスナーの皆さんが、日本語を楽しく学んでいる姿は本当に**素敵**です。",
                      f"The sight of listeners worldwide learning Japanese enjoyably is truly wonderful."),
            ("Host1", f"毎回のリスニングの時間が、皆さんの未来への大切な**ステップ**ですね。",
                      f"Each listening time is an important step toward everyone's future."),
            ("Host2", f"これからも一緒に、楽しく分かりやすいレッスンを続けて**いきましょう**。",
                      f"Let's continue enjoyable and easy-to-understand lessons together from now on."),
            ("Host1", f"はい、皆さんの学習を全力で応援して**います**！",
                      f"Yes, we are supporting everyone's study with all our strength!")
        ],
        # Phase 9: Vocabulary review
        [
            ("Host2", f"それでは、今日**{topic_es}**に関して登場した重要単語を復習しましょう。",
                      f"Now then, let's review the important words that appeared today regarding {topic_en}."),
            ("Host1", f"はい！一つ目のキーワードは**習慣**です。毎日コツコツ続ける良い行動のことですね。",
                      f"Yes! The first keyword is 'habit'. It refers to good actions steadily continued every day."),
            ("Host2", f"二つ目の単語は**品質**です。丁寧で確かな価値を表す大切な言葉です。",
                      f"The second word is 'quality'. An important word expressing careful and solid value."),
            ("Host1", f"三つ目の単語は**会話**です。相手と心を通わせて話す楽しさがあります。",
                      f"The third word is 'conversation'. There is joy in communicating hearts with a partner."),
            ("Host2", f"四つ目の言葉は**練習**です。少しずつの反復が大きな成果を生みます。",
                      f"The fourth word is 'practice'. A little repetition yields big results."),
            ("Host1", f"そして五つ目の言葉は**自信**です。勇気を持って話す力になります。",
                      f"And the fifth word is 'confidence'. It becomes the power to speak with courage."),
            ("Host2", f"リスナーの皆さんも、これらの単語を使ってコメント欄に例文を**書いて**みてください。",
                      f"Listeners, please also try writing an example sentence in the comments using these words."),
            ("Host1", f"皆さんのコメントを読むのを、私たちはいつも楽しみに**待っています**。",
                      f"We are always looking forward to reading your comments."),
            ("Host2", f"アウトプットすることで、学習した内容が頭にしっかりと**定着**します。",
                      f"By outputting, the learned content firmly fixes in your mind."),
            ("Host1", f"それでは、いよいよ本日のまとめの**時間**です。",
                      f"Now then, it's finally time for today's summary.")
        ],
        # Phase 10: Conclusion & wrap-up
        [
            ("Host2", f"今日の**{topic_es}**についてのポッドキャストも、終わりの時間が近づいてきました。",
                      f"Today's podcast about {topic_en} is also approaching its ending time."),
            ("Host1", f"楽しい時間はあっという間ですね！たくさんの役立つ表現を**紹介**できました。",
                      f"Fun time passes in a flash! We were able to introduce many useful expressions."),
            ("Host2", f"この音声を何度も聴き直して、自然な発音とリズムを身につけて**ください**。",
                      f"Please listen back to this audio many times to acquire natural pronunciation and rhythm."),
            ("Host1", f"繰り返し聴くことで、日本語がもっと身近に、そして楽しく**感じられます**。",
                      f"By listening repeatedly, Japanese feels much closer and more enjoyable."),
            ("Host2", f"いつも応援してくださるリスナーの皆様に、心から**感謝**いたします。",
                      f"We thank from our hearts all listeners who always support us."),
            ("Host1", f"チャンネル登録と高評価、そしてお友達へのシェアもぜひ**よろしく**お願いします。",
                      f"Please subscribe to the channel, like the video, and share with your friends."),
            ("Host2", f"次回も皆さんの役に立つ面白いトピックを用意して**お待ちしています**。",
                      f"Next time too we will prepare an interesting topic helpful to you all."),
            ("Host1", f"今日も素晴らしい一日をお過ごし**ください**！",
                      f"Please have a wonderful day today as well!"),
            ("Host2", f"それでは皆さん、また次回の配信でお会い**しましょう**！",
                      f"Well then everyone, let's meet again in the next broadcast!"),
            ("Host1", f"さようなら、笑顔で日本語を話して**いきましょう**！",
                      f"Goodbye, let's keep speaking Japanese with a smile!")
        ]
    ]

    all_templates = []
    for ph in phases:
        all_templates.extend(ph)
    turns = []
    for i in range(target):
        _, t_ja, t_en = all_templates[i % len(all_templates)]
        spk = "Host2" if i % 2 == 0 else "Host1"
        turns.append({
            "speaker": spk,
            "japanese": t_ja,
            "romaji": to_accurate_romaji(t_ja),
            "english": t_en
        })
    return turns


def _extend_script(existing_turns, topic_es, topic_en, target=150):
    fallback_pool = _fallback_script(topic_es, topic_en, target)
    idx = 0
    cur_speaker = existing_turns[-1]["speaker"] if existing_turns else "Host1"
    while len(existing_turns) < target:
        cand = fallback_pool[idx % len(fallback_pool)]
        idx += 1
        needed_spk = "Host1" if cur_speaker == "Host2" else "Host2"
        existing_turns.append({
            "speaker": needed_spk,
            "japanese": cand["japanese"],
            "romaji": cand["romaji"],
            "english": cand["english"]
        })
        cur_speaker = needed_spk
    return existing_turns[:target]


def generate_script():
    topic = _generate_topic() or random.choice(TOPICS)
    topic_es = topic.split(" - ")[0]
    topic_en = topic.split(" - ")[1]

    TARGET = 150
    BATCH = 10
    all_turns = []
    consecutive_empty = 0
    import time as _time
    _deadline = _time.time() + 600  # generous 10 min cap

    while len(all_turns) < TARGET and consecutive_empty < 12 and _time.time() < _deadline:
        batch = _fetch_turns_batch(topic, topic_es, topic_en, len(all_turns), BATCH)
        if not batch:
            consecutive_empty += 1
            wait_s = min(15, 3 + consecutive_empty * 2)
            print(f"  API busy (consecutive fails: {consecutive_empty}) - waiting {wait_s}s before retrying...", flush=True)
            _time.sleep(wait_s)
            continue
        all_turns.extend(batch)
        consecutive_empty = 0
        print(f"  Script progress: {len(all_turns)}/{TARGET} turns", flush=True)
        if len(all_turns) < TARGET:
            _time.sleep(1)

    all_turns = all_turns[:TARGET]

    if not all_turns:
        print("  Using structured fallback script (150 unique turns)...", flush=True)
        all_turns = _fallback_script(topic_es, topic_en, TARGET)
    elif len(all_turns) < TARGET:
        print(f"  Extending {len(all_turns)} turns to {TARGET} with topic conversation...", flush=True)
        all_turns = _extend_script(all_turns, topic_es, topic_en, TARGET)

    # Short 2-line intro: Kenji (Host2) first, then Hana (Host1), then topic
    topic_romaji = to_accurate_romaji(topic_es)
    all_turns[0]["speaker"] = "Host2"
    all_turns[0]["japanese"] = f"こんにちは、健二です。Velocity Japaneseへようこそ。今日は**{topic_es}**について話します。"
    all_turns[0]["romaji"] = f"Konnichiwa, Kenji desu. Velocity Japanese e yōkoso. Kyō wa {topic_romaji} ni tsuite hanashimasu."
    all_turns[0]["english"] = f"Hi, I'm Kenji. Welcome to Velocity Japanese Podcast. Today we talk about {topic_en}."
    if len(all_turns) > 1:
        all_turns[1]["speaker"] = "Host1"
        all_turns[1]["japanese"] = f"ありがとう、健二さん。今日のテーマはとても**面白い**です。始めましょう。"
        all_turns[1]["romaji"] = f"Arigatō, Kenji-san. Kyō no tēma wa totemo **omoshiroi** desu. Hajimemashō."
        all_turns[1]["english"] = f"Thanks, Kenji. Today's topic is very interesting. Let's start."

    # Final guarantee across ALL turns: ensure valid Latin romaji exists for every single turn
    for turn in all_turns:
        ja = turn.get("japanese", "")
        ro = sanitize_latin(turn.get("romaji", ""))
        if not re.search(r'[a-zA-Z]{2,}', ro):
            turn["romaji"] = to_accurate_romaji(ja)
        else:
            turn["romaji"] = ro

    print(f"  Script: {len(all_turns)} turns, topic: {topic_es}", flush=True)
    return all_turns, topic_es, topic_en


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