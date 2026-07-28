"""
Генератор плана квартиры на OpenCV.

Вся геометрия (стены, двери, окна, мебель, размерные линии) рисуется
средствами OpenCV. Pillow используется только для растеризации кириллических
подписей, потому что шрифты Hershey в cv2.putText не содержат кириллицы
(модуль cv2.freetype в сборках opencv-python отсутствует).

Запуск:  python3 apartment_plan.py [-o apartment_plan.png]
"""

import argparse

import cv2
import numpy as np

# --------------------------------------------------------------------------
# Масштаб и геометрия холста
# --------------------------------------------------------------------------
S = 80                      # пикселей на метр (масштаб 1:100 при ~80 dpi)
FLAT_W, FLAT_H = 12.0, 9.0  # габариты квартиры в метрах

MARGIN_L, MARGIN_T = 175, 150
MARGIN_R, MARGIN_B = 115, 200

CANVAS_W = int(MARGIN_L + FLAT_W * S + MARGIN_R)
CANVAS_H = int(MARGIN_T + FLAT_H * S + MARGIN_B)

W_EXT = 0.30                # толщина наружных стен, м
W_INT = 0.12                # толщина внутренних перегородок, м

# --------------------------------------------------------------------------
# Палитра (BGR)
# --------------------------------------------------------------------------
BG = (250, 249, 246)
WALL = (40, 40, 44)
GRID = (238, 236, 232)
FURN_LINE = (128, 126, 130)
FURN_FILL = (247, 246, 244)
DIM = (120, 118, 122)
DOOR = (95, 93, 98)
WINDOW = (150, 120, 60)
TEXT_MAIN = (45, 45, 50)
TEXT_SUB = (120, 118, 122)
ACCENT = (140, 95, 40)

ROOM_COLORS = {
    "living": (233, 240, 248),
    "kitchen": (228, 243, 233),
    "bed1": (245, 236, 228),
    "bed2": (243, 233, 240),
    "bath": (240, 238, 220),
    "hall": (238, 238, 240),
    "corr": (243, 243, 245),
    "office": (229, 238, 247),
}


# --------------------------------------------------------------------------
# Преобразование координат: метры -> пиксели
# --------------------------------------------------------------------------
def px(x, y):
    return int(round(MARGIN_L + x * S)), int(round(MARGIN_T + y * S))


def pxl(v):
    """Длина в метрах -> длина в пикселях."""
    return int(round(v * S))


# --------------------------------------------------------------------------
# Слой текста (Pillow поверх numpy-массива OpenCV)
# --------------------------------------------------------------------------
class TextLayer:
    """Накапливает подписи и отрисовывает их одним проходом в конце."""

    REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    def __init__(self):
        self.items = []

    def add(self, text, x, y, size=18, color=TEXT_MAIN, bold=False,
            anchor="mm", angle=0):
        """Координаты x, y — в метрах плана. anchor как в Pillow ('mm', 'lt'...)."""
        self.items.append(dict(text=text, pos=px(x, y), size=size, color=color,
                               bold=bold, anchor=anchor, angle=angle))

    def add_px(self, text, x, y, size=18, color=TEXT_MAIN, bold=False,
               anchor="mm", angle=0):
        """То же, но координаты сразу в пикселях холста."""
        self.items.append(dict(text=text, pos=(int(x), int(y)), size=size,
                               color=color, bold=bold, anchor=anchor, angle=angle))

    def render(self, img):
        from PIL import Image, ImageDraw, ImageFont

        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        cache = {}

        for it in self.items:
            key = (it["bold"], it["size"])
            if key not in cache:
                path = self.BOLD if it["bold"] else self.REGULAR
                cache[key] = ImageFont.truetype(path, it["size"])
            font = cache[key]
            b, g, r = it["color"]
            rgb = (r, g, b)

            if it["angle"]:
                # Повёрнутый текст рисуем на отдельном прозрачном слое.
                bbox = draw.textbbox((0, 0), it["text"], font=font)
                tw, th = bbox[2] - bbox[0] + 8, bbox[3] - bbox[1] + 8
                tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
                ImageDraw.Draw(tile).text((4 - bbox[0], 4 - bbox[1]),
                                          it["text"], font=font, fill=rgb + (255,))
                tile = tile.rotate(it["angle"], expand=True,
                                   resample=Image.BICUBIC)
                x, y = it["pos"]
                pil.paste(tile, (x - tile.width // 2, y - tile.height // 2), tile)
            else:
                draw.text(it["pos"], it["text"], font=font, fill=rgb,
                          anchor=it["anchor"])

        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


T = TextLayer()


# --------------------------------------------------------------------------
# Базовые примитивы
# --------------------------------------------------------------------------
def rect(img, x1, y1, x2, y2, color, thickness=-1, lt=cv2.LINE_AA):
    cv2.rectangle(img, px(x1, y1), px(x2, y2), color, thickness, lt)


def line(img, x1, y1, x2, y2, color, thickness=2, lt=cv2.LINE_AA):
    cv2.line(img, px(x1, y1), px(x2, y2), color, thickness, lt)


def circle(img, x, y, r, color, thickness=2):
    cv2.circle(img, px(x, y), pxl(r), color, thickness, cv2.LINE_AA)


def wall(img, x1, y1, x2, y2, t=W_INT):
    """Стена задаётся осевой линией и толщиной."""
    if abs(y1 - y2) < 1e-9:                      # горизонтальная
        rect(img, min(x1, x2), y1 - t / 2, max(x1, x2), y1 + t / 2, WALL, -1)
    else:                                        # вертикальная
        rect(img, x1 - t / 2, min(y1, y2), x1 + t / 2, max(y1, y2), WALL, -1)


def erase(img, x1, y1, x2, y2, color=BG):
    rect(img, x1, y1, x2, y2, color, -1, cv2.LINE_8)


# --------------------------------------------------------------------------
# Двери и окна
# --------------------------------------------------------------------------
def door(img, axis, pos, a, b, t=W_INT, hinge="a", swing=1, leaf=True):
    """
    Дверь в проёме стены.
      axis  — 'h' (горизонтальная стена, pos = y) или 'v' (pos = x)
      a, b  — границы проёма вдоль стены, м
      hinge — 'a' или 'b': у какого края петли
      swing — +1 / -1: в какую сторону открывается
      leaf  — False для открытого проёма без полотна
    """
    half = t / 2 + 0.005
    if axis == "h":
        erase(img, a, pos - half, b, pos + half)
        # притолоки по краям проёма
        line(img, a, pos - half, a, pos + half, WALL, 2)
        line(img, b, pos - half, b, pos + half, WALL, 2)
        if not leaf:
            return
        hx = a if hinge == "a" else b
        ox = b if hinge == "a" else a
        h = np.array(px(hx, pos), float)
        o = np.array(px(ox, pos), float)
        leaf_end = np.array(px(hx, pos + swing * abs(b - a)), float)
    else:
        erase(img, pos - half, a, pos + half, b)
        line(img, pos - half, a, pos + half, a, WALL, 2)
        line(img, pos - half, b, pos + half, b, WALL, 2)
        if not leaf:
            return
        hy = a if hinge == "a" else b
        oy = b if hinge == "a" else a
        h = np.array(px(pos, hy), float)
        o = np.array(px(pos, oy), float)
        leaf_end = np.array(px(pos + swing * abs(b - a), hy), float)

    r = int(round(np.linalg.norm(o - h)))
    a0 = np.degrees(np.arctan2(o[1] - h[1], o[0] - h[0]))
    a1 = np.degrees(np.arctan2(leaf_end[1] - h[1], leaf_end[0] - h[0]))
    start = min(a0, a1) if abs(a0 - a1) <= 180 else max(a0, a1)
    center = (int(h[0]), int(h[1]))

    cv2.ellipse(img, center, (r, r), 0, start, start + 90, DOOR, 1, cv2.LINE_AA)
    cv2.line(img, center, (int(leaf_end[0]), int(leaf_end[1])), DOOR, 4, cv2.LINE_AA)


def window(img, axis, pos, a, b, t=W_EXT):
    """Окно: проём в стене с тройной линией остекления."""
    half = t / 2
    if axis == "h":
        erase(img, a, pos - half, b, pos + half, (255, 255, 255))
        line(img, a, pos - half, b, pos - half, WALL, 2)
        line(img, a, pos + half, b, pos + half, WALL, 2)
        line(img, a, pos, b, pos, WINDOW, 3)
        line(img, a, pos - half, a, pos + half, WALL, 2)
        line(img, b, pos - half, b, pos + half, WALL, 2)
    else:
        erase(img, pos - half, a, pos + half, b, (255, 255, 255))
        line(img, pos - half, a, pos - half, b, WALL, 2)
        line(img, pos + half, a, pos + half, b, WALL, 2)
        line(img, pos, a, pos, b, WINDOW, 3)
        line(img, pos - half, a, pos + half, a, WALL, 2)
        line(img, pos - half, b, pos + half, b, WALL, 2)


# --------------------------------------------------------------------------
# Мебель и сантехника
# --------------------------------------------------------------------------
def furn(img, x1, y1, x2, y2, fill=FURN_FILL, r=0.06):
    """Прямоугольник мебели со скруглением углов."""
    p1, p2 = px(x1, y1), px(x2, y2)
    rr = pxl(r)
    sub = img[p1[1]:p2[1], p1[0]:p2[0]]
    if sub.size == 0:
        return
    w, h = p2[0] - p1[0], p2[1] - p1[1]
    mask = np.zeros((h, w), np.uint8)
    cv2.rectangle(mask, (rr, 0), (w - rr, h), 255, -1)
    cv2.rectangle(mask, (0, rr), (w, h - rr), 255, -1)
    for cx, cy in ((rr, rr), (w - rr, rr), (rr, h - rr), (w - rr, h - rr)):
        cv2.circle(mask, (cx, cy), rr, 255, -1)
    sub[mask > 0] = fill
    edge = cv2.dilate(cv2.Canny(mask, 50, 150), np.ones((2, 2), np.uint8))
    sub[edge > 0] = FURN_LINE


def sofa(img, x, y, w, h, facing="down"):
    """Диван: спинка со стороны, противоположной facing, подлокотники по бокам."""
    back, arm = (236, 234, 232), (236, 234, 232)
    cush = (243, 241, 239)
    d = 0.20
    furn(img, x, y, x + w, y + h)

    if facing in ("down", "up"):
        if facing == "down":
            furn(img, x, y, x + w, y + d, back)
            c1, c2 = y + d + 0.04, y + h - 0.06
        else:
            furn(img, x, y + h - d, x + w, y + h, back)
            c1, c2 = y + 0.06, y + h - d - 0.04
        furn(img, x, y, x + d, y + h, arm)
        furn(img, x + w - d, y, x + w, y + h, arm)
        n = max(1, int(round((w - 2 * d) / 0.75)))
        for i in range(n):
            a = x + d + (w - 2 * d) * i / n
            b = x + d + (w - 2 * d) * (i + 1) / n
            furn(img, a + 0.04, c1, b - 0.04, c2, cush, 0.04)
    else:
        if facing == "right":
            furn(img, x, y, x + d, y + h, back)
            c1, c2 = x + d + 0.04, x + w - 0.06
        else:
            furn(img, x + w - d, y, x + w, y + h, back)
            c1, c2 = x + 0.06, x + w - d - 0.04
        furn(img, x, y, x + w, y + d, arm)
        furn(img, x, y + h - d, x + w, y + h, arm)
        n = max(1, int(round((h - 2 * d) / 0.75)))
        for i in range(n):
            a = y + d + (h - 2 * d) * i / n
            b = y + d + (h - 2 * d) * (i + 1) / n
            furn(img, c1, a + 0.04, c2, b - 0.04, cush, 0.04)


def bed(img, x, y, w, h):
    """Кровать: изголовье сверху, подушки, покрывало."""
    furn(img, x, y, x + w, y + h)
    furn(img, x, y, x + w, y + 0.16, (230, 228, 226), 0.03)      # изголовье
    n = 2 if w > 1.4 else 1
    for i in range(n):
        pw = (w - 0.2) / n
        pxs = x + 0.1 + i * pw
        furn(img, pxs + 0.05, y + 0.22, pxs + pw - 0.05, y + 0.72,
             (238, 236, 234), 0.08)
    line(img, x + 0.05, y + 0.95, x + w - 0.05, y + 0.95, FURN_LINE, 1)
    furn(img, x + 0.05, y + 0.98, x + w - 0.05, y + h - 0.05,
         (241, 239, 237), 0.05)


def table_round(img, cx, cy, r, chairs=4):
    circle(img, cx, cy, r, FURN_FILL, -1)
    circle(img, cx, cy, r, FURN_LINE, 2)
    for i in range(chairs):
        ang = 2 * np.pi * i / chairs + np.pi / 4
        chx, chy = cx + (r + 0.32) * np.cos(ang), cy + (r + 0.32) * np.sin(ang)
        circle(img, chx, chy, 0.21, FURN_FILL, -1)
        circle(img, chx, chy, 0.21, FURN_LINE, 2)


def kitchen_unit(img, x1, y1, x2, y2, horizontal=True):
    furn(img, x1, y1, x2, y2, (240, 239, 236), 0.03)
    n = max(1, int(round((x2 - x1 if horizontal else y2 - y1) / 0.6)))
    for i in range(1, n):
        if horizontal:
            t = x1 + (x2 - x1) * i / n
            line(img, t, y1, t, y2, FURN_LINE, 1)
        else:
            t = y1 + (y2 - y1) * i / n
            line(img, x1, t, x2, t, FURN_LINE, 1)


def stove(img, x, y, w=0.6, h=0.6):
    furn(img, x, y, x + w, y + h, (238, 237, 234), 0.03)
    for dx, dy in ((0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)):
        circle(img, x + w * dx, y + h * dy, 0.11, FURN_LINE, 2)


def sink(img, cx, cy, w=0.55, h=0.45):
    furn(img, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, (236, 240, 243), 0.05)
    circle(img, cx, cy + 0.02, 0.09, FURN_LINE, 2)
    line(img, cx, cy - h / 2 + 0.03, cx, cy - h / 2 + 0.12, FURN_LINE, 2)


def bathtub(img, x, y, w, h):
    furn(img, x, y, x + w, y + h, (236, 240, 243), 0.08)
    furn(img, x + 0.09, y + 0.09, x + w - 0.09, y + h - 0.09, (247, 250, 252), 0.10)
    circle(img, x + w - 0.26, y + h / 2, 0.06, FURN_LINE, 2)


def toilet(img, cx, cy):
    furn(img, cx - 0.19, cy - 0.36, cx + 0.19, cy - 0.18, (236, 240, 243), 0.03)
    circle(img, cx, cy + 0.04, 0.20, (236, 240, 243), -1)
    circle(img, cx, cy + 0.04, 0.20, FURN_LINE, 2)


def wardrobe(img, x1, y1, x2, y2, horizontal=True):
    furn(img, x1, y1, x2, y2, (238, 236, 233), 0.03)
    if horizontal:
        n = max(2, int(round((x2 - x1) / 0.55)))
        for i in range(1, n):
            t = x1 + (x2 - x1) * i / n
            line(img, t, y1, t, y2, FURN_LINE, 1)
        line(img, x1, (y1 + y2) / 2, x2, (y1 + y2) / 2, FURN_LINE, 1)
    else:
        n = max(2, int(round((y2 - y1) / 0.55)))
        for i in range(1, n):
            t = y1 + (y2 - y1) * i / n
            line(img, x1, t, x2, t, FURN_LINE, 1)
        line(img, (x1 + x2) / 2, y1, (x1 + x2) / 2, y2, FURN_LINE, 1)


# --------------------------------------------------------------------------
# Размерные линии
# --------------------------------------------------------------------------
def dim_chain(img, axis, pos, stops, label_size=15):
    """
    Размерная цепочка в архитектурном стиле (засечки под 45°).
      axis  — 'h' (горизонтальная цепочка, pos = y) / 'v' (pos = x)
      stops — список координат в метрах
    """
    tick = 0.09
    if axis == "h":
        line(img, stops[0], pos, stops[-1], pos, DIM, 1)
        for s in stops:
            line(img, s - tick, pos + tick, s + tick, pos - tick, DIM, 1)
            line(img, s, pos, s, pos + (0.35 if pos < 0 else -0.35), GRID, 1)
        for a, b in zip(stops, stops[1:]):
            T.add(f"{b - a:.2f}", (a + b) / 2, pos - 0.16, label_size, DIM)
    else:
        line(img, pos, stops[0], pos, stops[-1], DIM, 1)
        for s in stops:
            line(img, pos + tick, s - tick, pos - tick, s + tick, DIM, 1)
            line(img, pos, s, pos + (0.35 if pos < 0 else -0.35), s, GRID, 1)
        for a, b in zip(stops, stops[1:]):
            T.add(f"{b - a:.2f}", pos - 0.16, (a + b) / 2, label_size, DIM,
                  angle=90)


# --------------------------------------------------------------------------
# Сборка плана
# --------------------------------------------------------------------------
ROOMS = [
    # (ключ цвета, x1, y1, x2, y2, название)
    ("living",  0.0, 0.0,  6.0, 4.5, "ГОСТИНАЯ"),
    ("kitchen", 6.0, 0.0,  9.0, 4.5, "КУХНЯ"),
    ("bed1",    9.0, 0.0, 12.0, 4.5, "СПАЛЬНЯ 1"),
    ("hall",    0.0, 4.5,  2.6, 9.0, "ПРИХОЖАЯ"),
    ("corr",    2.6, 4.5, 12.0, 5.9, "КОРИДОР"),
    ("bath",    2.6, 5.9,  4.8, 9.0, "САНУЗЕЛ"),
    ("bed2",    4.8, 5.9,  9.0, 9.0, "СПАЛЬНЯ 2"),
    ("office",  9.0, 5.9, 12.0, 9.0, "КАБИНЕТ"),
]


def draw_floors(img):
    for key, x1, y1, x2, y2, _ in ROOMS:
        rect(img, x1, y1, x2, y2, ROOM_COLORS[key], -1)
    # лёгкая сетка 1 м для читаемости масштаба
    for i in range(1, int(FLAT_W)):
        line(img, i, 0, i, FLAT_H, GRID, 1)
    for i in range(1, int(FLAT_H)):
        line(img, 0, i, FLAT_W, i, GRID, 1)


def draw_furniture(img):
    # --- Гостиная -----------------------------------------------------------
    sofa(img, 1.30, 1.65, 2.60, 0.95, "down")
    furn(img, 2.00, 2.95, 3.20, 3.50, (242, 240, 238), 0.05)         # журн. стол
    furn(img, 0.45, 1.90, 1.15, 2.70)                                # кресло
    furn(img, 4.35, 1.90, 5.05, 2.70)                                # кресло 2
    furn(img, 2.00, 4.00, 3.90, 4.30, (238, 236, 233), 0.03)         # ТВ-тумба
    furn(img, 2.60, 4.05, 3.30, 4.13, (215, 213, 210), 0.02)         # телевизор
    wardrobe(img, 5.35, 0.60, 5.85, 2.60, False)                     # стеллаж
    circle(img, 5.40, 3.60, 0.38, (238, 243, 236), -1)               # растение
    circle(img, 5.40, 3.60, 0.38, FURN_LINE, 2)

    # --- Кухня --------------------------------------------------------------
    kitchen_unit(img, 6.25, 0.30, 8.85, 0.90, True)                  # верхний ряд
    sink(img, 6.85, 0.60)
    stove(img, 7.75, 0.30)
    furn(img, 8.25, 0.30, 8.85, 0.90, (233, 238, 241), 0.03)         # холодильник
    kitchen_unit(img, 8.30, 1.05, 8.85, 2.20, False)                 # боковой ряд
    furn(img, 6.25, 1.15, 7.30, 1.45, (240, 239, 236), 0.03)         # остров
    table_round(img, 7.45, 3.15, 0.60, 4)

    # --- Спальня 1 ----------------------------------------------------------
    bed(img, 9.70, 0.35, 1.60, 2.05)
    furn(img, 9.22, 0.35, 9.62, 0.85)                                # тумбы
    furn(img, 11.38, 0.35, 11.78, 0.85)
    wardrobe(img, 10.35, 3.45, 11.78, 4.05, True)
    furn(img, 9.22, 2.55, 10.05, 3.00, (242, 240, 238), 0.04)        # комод

    # --- Спальня 2 ----------------------------------------------------------
    bed(img, 5.30, 6.25, 1.55, 1.95)
    furn(img, 4.95, 6.25, 5.25, 6.72)                                # тумба
    furn(img, 7.35, 6.25, 8.85, 6.75, (242, 240, 238), 0.04)         # стол
    circle(img, 8.10, 7.10, 0.22, FURN_FILL, -1)                     # стул
    circle(img, 8.10, 7.10, 0.22, FURN_LINE, 2)
    wardrobe(img, 8.32, 7.60, 8.85, 8.70, False)

    # --- Санузел ------------------------------------------------------------
    bathtub(img, 2.78, 8.05, 1.72, 0.73)
    sink(img, 4.42, 6.35, 0.55, 0.45)
    toilet(img, 2.98, 6.45)
    furn(img, 2.78, 7.05, 3.38, 7.65, (236, 240, 243), 0.03)         # стиральная
    circle(img, 3.08, 7.35, 0.19, FURN_LINE, 2)

    # --- Кабинет ------------------------------------------------------------
    furn(img, 9.25, 6.20, 11.05, 6.85, (242, 240, 238), 0.04)        # стол
    circle(img, 10.15, 7.25, 0.23, FURN_FILL, -1)
    circle(img, 10.15, 7.25, 0.23, FURN_LINE, 2)
    wardrobe(img, 9.25, 8.25, 11.00, 8.72, True)                     # стеллаж
    sofa(img, 11.10, 6.85, 0.72, 1.50, "left")

    # --- Прихожая -----------------------------------------------------------
    wardrobe(img, 1.85, 4.85, 2.42, 6.65, False)                     # шкаф-купе
    furn(img, 0.30, 8.10, 1.60, 8.55, (242, 240, 238), 0.04)         # обувница
    furn(img, 0.30, 4.80, 0.75, 5.90, (242, 240, 238), 0.04)         # консоль

    # --- Коридор ------------------------------------------------------------
    furn(img, 5.10, 4.75, 6.60, 5.05, (242, 240, 238), 0.03)         # шкаф-пенал


def draw_walls(img):
    # наружный контур
    wall(img, 0, 0, FLAT_W, 0, W_EXT)
    wall(img, 0, FLAT_H, FLAT_W, FLAT_H, W_EXT)
    wall(img, 0, 0, 0, FLAT_H, W_EXT)
    wall(img, FLAT_W, 0, FLAT_W, FLAT_H, W_EXT)

    # внутренние перегородки
    wall(img, 0.0, 4.5, 12.0, 4.5)      # верхний ряд / коридор
    wall(img, 2.6, 5.9, 12.0, 5.9)      # коридор / нижний ряд
    wall(img, 6.0, 0.0, 6.0, 4.5)       # гостиная / кухня
    wall(img, 9.0, 0.0, 9.0, 4.5)       # кухня / спальня 1
    wall(img, 2.6, 4.5, 2.6, 9.0)       # прихожая
    wall(img, 4.8, 5.9, 4.8, 9.0)       # санузел / спальня 2
    wall(img, 9.0, 5.9, 9.0, 9.0)       # спальня 2 / кабинет


def draw_openings(img):
    # входная дверь
    door(img, "v", 0.0, 6.60, 7.50, W_EXT, hinge="a", swing=1)
    T.add("вход", 0.42, 7.05, 13, ACCENT, angle=90)

    # межкомнатные двери
    door(img, "h", 4.5, 1.00, 1.90, hinge="b", swing=-1)   # гостиная-прихожая
    door(img, "h", 4.5, 3.60, 4.50, hinge="a", swing=1)    # гостиная-коридор
    door(img, "h", 4.5, 7.00, 7.90, hinge="b", swing=-1)   # кухня-коридор
    door(img, "h", 4.5, 9.30, 10.20, hinge="b", swing=-1)  # спальня 1
    door(img, "h", 5.9, 3.30, 4.10, hinge="a", swing=1)    # санузел
    door(img, "h", 5.9, 6.40, 7.30, hinge="b", swing=1)    # спальня 2
    door(img, "h", 5.9, 10.10, 11.00, hinge="a", swing=1)  # кабинет
    door(img, "v", 2.6, 4.90, 5.70, leaf=False)            # открытый проём

    # окна
    window(img, "h", 0.0, 1.00, 2.80)
    window(img, "h", 0.0, 3.40, 5.20)
    window(img, "h", 0.0, 6.70, 8.40)
    window(img, "h", 0.0, 9.80, 11.40)
    window(img, "v", 0.0, 1.20, 3.20)
    window(img, "v", 12.0, 1.20, 3.20)
    window(img, "v", 12.0, 6.60, 8.40)
    window(img, "h", 9.0, 5.60, 7.40)
    window(img, "h", 9.0, 3.30, 4.10)


def draw_labels(img):
    for key, x1, y1, x2, y2, name in ROOMS:
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        area = (x2 - x1) * (y2 - y1)
        if key == "living":
            cx, cy = 3.00, 1.00
        elif key == "kitchen":
            cx, cy = 7.45, 1.95
        elif key == "bed1":
            cx, cy = 10.95, 2.95
        elif key == "hall":
            cx, cy = 1.55, 7.35
        elif key == "corr":
            cx, cy = 8.85, 5.20
        elif key == "bath":
            cx, cy = 3.92, 7.35
        elif key == "bed2":
            cx, cy = 6.55, 8.50
        elif key == "office":
            cx, cy = 10.05, 7.80

        size = 15 if key in ("corr", "bath", "hall") else 18
        T.add(name, cx, cy - 0.12, size, TEXT_MAIN, bold=True)
        T.add(f"{area:.1f} м²", cx, cy + 0.22, size - 3, TEXT_SUB)


def draw_dimensions(img):
    dim_chain(img, "h", -0.62, [0.0, 6.0, 9.0, 12.0])
    dim_chain(img, "h", -1.25, [0.0, 12.0])
    dim_chain(img, "v", -0.62, [0.0, 4.5, 5.9, 9.0])
    dim_chain(img, "v", -1.25, [0.0, 9.0])


def draw_titleblock(img):
    y0 = MARGIN_T + int(FLAT_H * S) + 42
    cv2.line(img, (MARGIN_L, y0 - 16), (MARGIN_L + int(FLAT_W * S), y0 - 16),
             (215, 213, 210), 2, cv2.LINE_AA)

    T.add_px("ПЛАН КВАРТИРЫ", MARGIN_L, y0, 30, TEXT_MAIN, bold=True, anchor="lt")
    total = sum((x2 - x1) * (y2 - y1) for _, x1, y1, x2, y2, _ in ROOMS)
    T.add_px(f"3 комнаты + кабинет  ·  общая площадь {total:.1f} м²  ·  "
             f"габариты {FLAT_W:.1f} × {FLAT_H:.1f} м  ·  масштаб 1:100",
             MARGIN_L, y0 + 40, 17, TEXT_SUB, anchor="lt")

    # масштабная линейка 0–5 м
    bx, by = MARGIN_L, y0 + 82
    seg = S
    for i in range(5):
        c = WALL if i % 2 == 0 else (255, 255, 255)
        cv2.rectangle(img, (bx + i * seg, by), (bx + (i + 1) * seg, by + 13),
                      c, -1)
    cv2.rectangle(img, (bx, by), (bx + 5 * seg, by + 13), WALL, 2)
    for i in (0, 1, 2, 3, 4, 5):
        T.add_px(str(i), bx + i * seg, by + 20, 13, TEXT_SUB, anchor="mt")
    T.add_px("м", bx + 5 * seg + 16, by + 20, 13, TEXT_SUB, anchor="lt")

    # условные обозначения
    lx = MARGIN_L + int(5.6 * S)
    items = [("стена", WALL), ("окно", WINDOW), ("дверь", DOOR),
             ("мебель", FURN_LINE)]
    for i, (name, color) in enumerate(items):
        ix = lx + i * 122
        iy = by + 1
        cv2.rectangle(img, (ix, iy), (ix + 24, iy + 11), color, -1)
        T.add_px(name, ix + 31, iy + 5, 14, TEXT_SUB, anchor="lm")

    # стрелка «север»
    nx, ny = CANVAS_W - MARGIN_R - 34, y0 + 44
    cv2.circle(img, (nx, ny), 30, (220, 218, 215), 2, cv2.LINE_AA)
    tri = np.array([[nx, ny - 24], [nx - 11, ny + 16], [nx, ny + 7],
                    [nx + 11, ny + 16]], np.int32)
    cv2.fillPoly(img, [tri], ACCENT, cv2.LINE_AA)
    T.add_px("С", nx, ny - 44, 15, ACCENT, bold=True, anchor="mm")


def build():
    img = np.full((CANVAS_H, CANVAS_W, 3), BG, np.uint8)
    draw_floors(img)
    draw_furniture(img)
    draw_walls(img)
    draw_openings(img)
    draw_labels(img)
    draw_dimensions(img)
    draw_titleblock(img)
    return T.render(img)


def main():
    ap = argparse.ArgumentParser(description="План квартиры на OpenCV")
    ap.add_argument("-o", "--out", default="apartment_plan.png")
    args = ap.parse_args()
    img = build()
    cv2.imwrite(args.out, img)
    print(f"Сохранено: {args.out}  ({img.shape[1]}x{img.shape[0]})")


if __name__ == "__main__":
    main()
