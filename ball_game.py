"""Planet Breaker - fly a small rocket around space, shooting planets apart while
the volcanic ones fire meteors back at you.

Controls:
    Left click   fire a bolt at the cursor
    Mouse drag   steer the ship
    Space        reset the ship
    N            skip to the next level
    R            randomize ship color
    Esc          quit
"""

import math
import random
import sys
from array import array

import pygame

WIDTH, HEIGHT = 800, 600
FPS = 60

BALL_R = 11
MIN_SPEED = 160.0
MAX_SPEED = 900.0
ACCEL = 130.0
DRAG_PULL = 1.35
DRAG_MAX = 420.0
PLANET_MIN_R = 26.0
PLANET_MAX_R = 46.0
PLANET_EDGE_PAD = 34
PLANET_DRIFT = (5.0, 15.0)
SS = 3
LIGHT_DIR = (-0.6, -0.8)
LEVEL_DELAY = 1.2
SHAKE_DECAY = 42.0

PROJ_R = 7
PROJ_LIFE = 5.0
PROJ_BOUNCES = 3
SHOT_SPREAD = 22.0
BOLT_R = 4
BOLT_SPEED = 720.0
BOLT_LIFE = 1.2
FIRE_DELAY = 0.16
LIVES = 3
INVULN = 1.3

BG = (10, 12, 26)
WALL = (70, 90, 140)
BALL_COLORS = [
    (250, 250, 255),
    (255, 150, 150),
    (150, 230, 170),
    (150, 190, 255),
    (255, 210, 110),
    (210, 150, 255),
]

# base colors and ring tint per planet kind
PLANET_STYLES = {
    "cratered": {"bases": [(152, 143, 132), (138, 128, 118), (166, 150, 130)],
                 "ring": None, "airless": True},
    "gas": {"bases": [(206, 152, 92), (168, 176, 214), (196, 140, 148), (150, 190, 160)],
            "ring": None, "airless": False},
    "ringed": {"bases": [(198, 176, 128), (176, 190, 206), (206, 186, 158)],
               "ring": (222, 208, 174), "airless": False},
    "ice": {"bases": [(158, 214, 230), (196, 226, 236), (140, 196, 220)],
            "ring": None, "airless": False},
    "lava": {"bases": [(104, 56, 50), (124, 62, 48)],
             "ring": None, "airless": False},
}
PLANET_KINDS = tuple(PLANET_STYLES)

STATE_PLAY = "play"
STATE_OVER = "over"


def make_beep(freq, ms, volume=0.25):
    """Generate a short tone in-memory so the game needs no sound files."""
    sample_rate = 44100
    samples = int(sample_rate * ms / 1000)
    buf = array("h")
    for i in range(samples):
        decay = 1.0 - (i / samples)
        val = math.sin(2 * math.pi * freq * i / sample_rate) * decay
        buf.append(int(max(-1.0, min(1.0, val)) * 32767 * volume))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def shift(color, f, alpha=None):
    out = tuple(max(0, min(255, int(ch * f))) for ch in color)
    return out + (alpha,) if alpha is not None else out


def draw_arc(surface, color, center, rx, ry, a0, a1, width):
    """Arc as a sampled polyline: pygame.draw.arc ignores start/stop angles.

    Angles follow the screen convention: 0 = right, 90 = down, 180 = left,
    270 = up.
    """
    steps = max(8, int(abs(a1 - a0) / 4))
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((center[0] + math.cos(a) * rx, center[1] + math.sin(a) * ry))
    pygame.draw.lines(surface, color, False, pts, width)


def render_stars():
    surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for _ in range(150):
        x = random.randrange(WIDTH)
        y = random.randrange(HEIGHT)
        b = random.randint(55, 210)
        pygame.draw.circle(surf, (b, b, min(255, b + 35), b), (x, y),
                           1 if b < 150 else 2)
    return surf


def render_planet(radius, kind, base):
    """Pre-render a shaded planet sprite plus optional ring halves."""
    style = PLANET_STYLES[kind]
    R = radius * SS
    has_ring = style["ring"] is not None
    size = int(R * (3.7 if has_ring else 2.0)) + 4
    center = (size // 2, size // 2)
    lx = LIGHT_DIR[0] * R
    ly = LIGHT_DIR[1] * R

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    alt = shift(base, 0.76)
    pygame.draw.circle(surf, base, center, R)

    if kind == "cratered":
        for _ in range(random.randint(4, 7)):
            a = random.uniform(0, math.tau)
            d = random.uniform(0, R * 0.6)
            cx = center[0] + math.cos(a) * d
            cy = center[1] + math.sin(a) * d
            cr = R * random.uniform(0.1, 0.21)
            pygame.draw.circle(surf, shift(base, 0.68), (cx, cy), cr)
            draw_arc(surf, shift(base, 1.35), (cx, cy), cr, cr,
                     185, 340, max(2, int(cr * 0.28)))
    elif kind == "gas":
        bands = random.randint(5, 7)
        y = center[1] - R - 2
        for i in range(bands):
            h = (R * 2 + 4) / bands * random.uniform(0.65, 1.35)
            pygame.draw.rect(surf, base if i % 2 else alt,
                             (center[0] - R - 2, y, R * 2 + 4, h))
            y += h
        sy = center[1] + random.uniform(-R * 0.45, R * 0.45)
        pygame.draw.ellipse(surf, shift(base, 1.3),
                            (center[0] - R * 0.34, sy - R * 0.13,
                             R * 0.68, R * 0.26))
    elif kind == "ice":
        for _ in range(random.randint(3, 5)):
            a = random.uniform(0, math.tau)
            d = random.uniform(0, R * 0.5)
            cx = center[0] + math.cos(a) * d
            cy = center[1] + math.sin(a) * d
            pts = [(cx, cy)]
            ang = random.uniform(0, math.tau)
            for _ in range(3):
                ang += random.uniform(-0.9, 0.9)
                step = R * random.uniform(0.15, 0.3)
                cx += math.cos(ang) * step
                cy += math.sin(ang) * step
                pts.append((cx, cy))
            pygame.draw.lines(surf, shift(base, 0.72), False, pts, max(2, int(R * 0.05)))
        pygame.draw.circle(surf, shift(base, 1.3),
                           (center[0], int(center[1] - R * 0.68)), R * 0.45)
    elif kind == "lava":
        for _ in range(4):
            a = random.uniform(0, math.tau)
            d = random.uniform(0, R * 0.45)
            cx = center[0] + math.cos(a) * d
            cy = center[1] + math.sin(a) * d
            pts = [(cx, cy)]
            ang = random.uniform(0, math.tau)
            for _ in range(3):
                ang += random.uniform(-1.0, 1.0)
                step = R * random.uniform(0.18, 0.34)
                cx += math.cos(ang) * step
                cy += math.sin(ang) * step
                pts.append((cx, cy))
            pygame.draw.lines(surf, shift(base, 0.6), False, pts, max(3, int(R * 0.09)))
            pygame.draw.lines(surf, (255, 190, 70), False, pts, max(1, int(R * 0.04)))

    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), center, R)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # terminator: shadow disc pushed away from the light, two steps for softness
    for off, alpha, shrink in ((0.3, 100, 1.0), (0.62, 72, 0.97)):
        sh = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0, 0, 0, alpha),
                           (int(center[0] - lx * off), int(center[1] - ly * off)),
                           R * shrink)
        sh.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(sh, (0, 0))

    # rim light along the lit limb
    draw_arc(surf, shift(base, 1.5), center, R - SS * 0.5, R - SS * 0.5,
             178, 272, max(2, int(R * 0.07)))
    if not style["airless"]:
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(glow, shift(base, 1.4, 70), center, R + SS * 1.5,
                           max(2, int(R * 0.08)))
        surf.blit(glow, (0, 0))

    out_size = max(2, int(round(size / SS)))
    img = pygame.transform.smoothscale(surf, (out_size, out_size))
    ring_back = ring_front = None
    if has_ring:
        rw = R * 1.72
        rh = R * 0.5
        thick = max(3, int(R * 0.09))
        ring_back = pygame.Surface((size, size), pygame.SRCALPHA)
        ring_front = pygame.Surface((size, size), pygame.SRCALPHA)
        draw_arc(ring_back, shift(style["ring"], 0.72), center, rw, rh,
                 180, 360, thick)
        draw_arc(ring_front, shift(style["ring"], 1.05), center, rw, rh,
                 0, 180, thick)
        draw_arc(ring_front, shift(style["ring"], 1.3), center, rw, rh,
                 0, 180, max(1, thick // 3))
        ring_back = pygame.transform.smoothscale(ring_back, (out_size, out_size))
        ring_front = pygame.transform.smoothscale(ring_front, (out_size, out_size))
    return img, ring_back, ring_front


class Ball:
    def __init__(self):
        self.pos = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.vel = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        self.vel = self.vel.normalize() * 320.0
        self.color = BALL_COLORS[0]

    def set_speed(self, speed):
        speed = max(MIN_SPEED, min(MAX_SPEED, speed))
        if self.vel.length() < 1e-6:
            angle = random.uniform(0, math.tau)
            self.vel = pygame.Vector2(math.cos(angle), math.sin(angle))
        self.vel = self.vel.normalize() * speed

    def update(self, dt, bouncing=True):
        self.pos += self.vel * dt
        self.set_speed(self.vel.length() + ACCEL * dt)

        if not bouncing:
            return None

        hit = None
        if self.pos.x < BALL_R:
            self.pos.x = BALL_R
            self.vel.x = abs(self.vel.x)
            hit = "wall"
        elif self.pos.x > WIDTH - BALL_R:
            self.pos.x = WIDTH - BALL_R
            self.vel.x = -abs(self.vel.x)
            hit = "wall"
        if self.pos.y < BALL_R:
            self.pos.y = BALL_R
            self.vel.y = abs(self.vel.y)
            hit = "wall"
        elif self.pos.y > HEIGHT - BALL_R:
            self.pos.y = HEIGHT - BALL_R
            self.vel.y = -abs(self.vel.y)
            hit = "wall"
        return hit


class Planet:
    """A round planet. Ball impacts crack it; some fire meteors at the ball."""

    def __init__(self, pos, radius, kind, max_hits, shooter=False,
                 interval=2.0, volley=1, proj_speed=140.0):
        self.pos = pygame.Vector2(pos)
        self.radius = radius
        self.kind = kind
        self.base = random.choice(PLANET_STYLES[kind]["bases"])
        self.crack = shift(self.base, 0.45)
        self.img, self.ring_back, self.ring_front = render_planet(radius, kind, self.base)
        self.hits = 0
        self.max_hits = max_hits
        self.flash = 0.0
        self.alive = True
        self.crack_rot = random.uniform(0, math.tau)
        speed = random.uniform(*PLANET_DRIFT)
        self.drift = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if self.drift.length() > 1e-6:
            self.drift = self.drift.normalize() * speed
        self.shooter = shooter
        self.interval = interval
        self.volley = volley
        self.proj_speed = proj_speed
        self.fire_timer = random.uniform(0.6, 2.4)

    @property
    def charge(self):
        if not self.shooter:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.fire_timer / self.interval))

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            return
        self.pos += self.drift * dt
        pad = self.radius + 6
        if self.pos.x < pad:
            self.pos.x = pad
            self.drift.x = abs(self.drift.x)
        elif self.pos.x > WIDTH - pad:
            self.pos.x = WIDTH - pad
            self.drift.x = -abs(self.drift.x)
        if self.pos.y < pad:
            self.pos.y = pad
            self.drift.y = abs(self.drift.y)
        elif self.pos.y > HEIGHT - pad:
            self.pos.y = HEIGHT - pad
            self.drift.y = -abs(self.drift.y)
        if self.shooter:
            self.fire_timer -= dt

    def collide(self, ball_pos, ball_r):
        """Overlap against the sphere as (outward normal, depth)."""
        off = ball_pos - self.pos
        dist = off.length()
        depth = ball_r + self.radius - dist
        if depth <= 0:
            return None, 0.0
        normal = off / dist if dist > 1e-6 else pygame.Vector2(0, -1)
        return normal, depth

    def fire(self, target):
        """Volley of meteors aimed at target."""
        aim = target - self.pos
        if aim.length() < 1e-6:
            aim = pygame.Vector2(0, -1)
        aim = aim.normalize()
        shots = []
        for i in range(self.volley):
            d = aim.rotate((i - (self.volley - 1) / 2) * SHOT_SPREAD)
            shots.append(Projectile(self.pos + d * (self.radius * 0.8),
                                    d * self.proj_speed))
        return shots

    def draw(self, surface):
        blit = (int(self.pos.x - self.img.get_width() / 2),
                int(self.pos.y - self.img.get_height() / 2))
        if self.ring_back is not None:
            surface.blit(self.ring_back, blit)
        img = self.img
        if self.flash > 0:
            img = self.img.copy()
            img.fill((130, 130, 130, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(img, blit)
        if self.hits:
            for i in range(self.hits):
                a = self.crack_rot + i * 2.1
                d = pygame.Vector2(math.cos(a), math.sin(a))
                pygame.draw.line(surface, self.crack,
                                 self.pos + d * (self.radius * 0.35),
                                 self.pos + d * (self.radius * 0.88), 3)
        if self.ring_front is not None:
            surface.blit(self.ring_front, blit)
        if self.shooter:
            t = self.charge
            if t > 0.04:
                ring = shift(self.base, 1.0 + 0.9 * t)
                pygame.draw.circle(surface, ring, (int(self.pos.x), int(self.pos.y)),
                                   int(self.radius + 8 + 14 * (1 - t)), 2)
                if t > 0.92:
                    pygame.draw.circle(surface, (255, 255, 255),
                                       (int(self.pos.x), int(self.pos.y)),
                                       int(self.radius * 0.3))


class Projectile:
    def __init__(self, pos, vel):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.r = PROJ_R
        self.bounces = 0
        self.life = PROJ_LIFE

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt
        if self.pos.x < self.r:
            self.pos.x = self.r
            self.vel.x = abs(self.vel.x)
            self.bounces += 1
        elif self.pos.x > WIDTH - self.r:
            self.pos.x = WIDTH - self.r
            self.vel.x = -abs(self.vel.x)
            self.bounces += 1
        if self.pos.y < self.r:
            self.pos.y = self.r
            self.vel.y = abs(self.vel.y)
            self.bounces += 1
        elif self.pos.y > HEIGHT - self.r:
            self.pos.y = HEIGHT - self.r
            self.vel.y = -abs(self.vel.y)
            self.bounces += 1
        return self.life > 0 and self.bounces <= PROJ_BOUNCES

    def draw(self, surface):
        cx, cy = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(surface, (255, 150, 40), (cx, cy), self.r + 3)
        pygame.draw.circle(surface, (255, 235, 180), (cx, cy), max(2, self.r - 2))


def draw_ship(surface, pos, heading, color, thrust=0.0):
    """Player rocket: nose points along heading, short flicker flame at the tail."""
    c = math.cos(heading)
    s = math.sin(heading)
    r = BALL_R

    def at(x, y):
        return (pos.x + (x * c - y * s) * r, pos.y + (x * s + y * c) * r)

    outline = [(1.2, 0.0), (0.2, -0.85), (-0.45, -1.05), (-0.7, -0.45),
               (-0.7, 0.45), (-0.45, 1.05), (0.2, 0.85)]
    hull = [at(x, y) for x, y in outline]
    pygame.draw.polygon(surface, shift(color, 0.5), hull, width=2)
    pygame.draw.polygon(surface, color, hull)
    nose = [at(1.2, 0.0), at(0.25, -0.5), at(0.25, 0.5)]
    pygame.draw.polygon(surface, shift(color, 1.35), nose)
    pygame.draw.circle(surface, (225, 240, 255), at(0.15, 0.0), max(2, r * 0.22))

    flick = 0.7 + 0.3 * math.sin(thrust * 40.0)
    length = (0.45 + 0.85 * flick) * (0.55 + 0.45 * min(1.0, thrust / MAX_SPEED))
    flame = [at(-0.7, -0.34), at(-0.7 - length, 0.0), at(-0.7, 0.34)]
    pygame.draw.polygon(surface, (255, 170, 60), flame)
    core = [at(-0.7, -0.17), at(-0.7 - length * 0.55, 0.0), at(-0.7, 0.17)]
    pygame.draw.polygon(surface, (255, 245, 200), core)


class Bolt:
    """Short laser streak fired by the ship."""

    def __init__(self, pos, vel, color):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.color = color
        self.r = BOLT_R
        self.life = BOLT_LIFE

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt
        if not (0 <= self.pos.x <= WIDTH and 0 <= self.pos.y <= HEIGHT):
            return False
        return self.life > 0

    def draw(self, surface):
        tail = self.pos - self.vel.normalize() * 11
        pygame.draw.line(surface, shift(self.color, 0.7), tail, self.pos, 3)
        pygame.draw.circle(surface, (255, 255, 255),
                           (int(self.pos.x), int(self.pos.y)), max(2, self.r // 2))


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Planet Breaker")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.world = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("consolas", 46, bold=True)
        self.font = pygame.font.SysFont("consolas", 20)
        self.small = pygame.font.SysFont("consolas", 16)
        self.stars = render_stars()

        pygame.mixer.pre_init(44100, -16, 1, 512)
        try:
            pygame.mixer.init()
            self.snd_wall = make_beep(520, 45)
            self.snd_hit = make_beep(240, 70, 0.2)
            self.snd_break = make_beep(760, 180, 0.3)
            self.snd_shoot = make_beep(980, 40, 0.12)
            self.snd_hurt = make_beep(180, 320, 0.35)
        except pygame.error:
            self.snd_wall = self.snd_hit = self.snd_break = None
            self.snd_shoot = self.snd_hurt = None

        self.ball = Ball()
        self.meteors = []
        self.bolts = []
        self.fire_cd = 0.0
        self.ship_heading = math.atan2(self.ball.vel.y, self.ball.vel.x)
        self.planets = []
        self.dragging = False
        self.state = STATE_PLAY
        self.new_game()

    def new_game(self):
        self.level = 1
        self.lives = LIVES
        self.score = 0
        self.broken = 0
        self.bounces = 0
        self.hits_dealt = 0
        self.invuln = 0.0
        self.shake = 0.0
        self.banner = ""
        self.banner_time = 0.0
        self.level_delay = 0.0
        self.state = STATE_PLAY
        self.spawn_level()

    def play(self, snd):
        if snd is not None:
            snd.play()

    def reset(self):
        self.ball.pos.update(WIDTH / 2, HEIGHT / 2)
        angle = random.uniform(0, math.tau)
        self.ball.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * 320.0
        self.ship_heading = angle
        self.bounces = 0
        self.invuln = 0.6
        self.bolts.clear()

    def randomize_color(self):
        choices = [c for c in BALL_COLORS if c != self.ball.color]
        self.ball.color = random.choice(choices)

    def difficulty(self):
        """Everything that ramps up per level."""
        lvl = self.level
        return {
            "count": 5 + min(3, lvl - 1),
            "shooters": min(6, 1 + (lvl - 1)),
            "interval": max(0.55, 2.3 - 0.16 * (lvl - 1)),
            "speed": min(520.0, 130.0 + 32.0 * (lvl - 1)),
            "volley": 1 + (1 if lvl >= 4 else 0) + (1 if lvl >= 8 else 0),
            "extra_hits": 1 if lvl >= 6 else 0,
        }

    def spawn_level(self):
        self.planets = []
        self.level_delay = 0.0
        self.level_broken = 0
        self.meteors.clear()
        diff = self.difficulty()
        for _ in range(600):
            if len(self.planets) >= diff["count"]:
                break
            r = random.uniform(PLANET_MIN_R, PLANET_MAX_R)
            pos = pygame.Vector2(
                random.uniform(r + PLANET_EDGE_PAD, WIDTH - r - PLANET_EDGE_PAD),
                random.uniform(r + PLANET_EDGE_PAD, HEIGHT - r - 46),
            )
            if any((pos - p.pos).length() < r + p.radius + 14 for p in self.planets):
                continue
            kind = random.choice(PLANET_KINDS)
            self.planets.append(Planet(pos, r, kind,
                                       random.choice((2, 2, 3)) + diff["extra_hits"],
                                       interval=diff["interval"],
                                       volley=diff["volley"],
                                       proj_speed=diff["speed"]))
        # shooters skew volcanic so they look like they can fire
        shooters = diff["shooters"]
        pool = [p for p in self.planets if p.kind == "lava"] + \
               [p for p in self.planets if p.kind != "lava"]
        for p in random.sample(pool, min(shooters, len(pool))):
            p.shooter = True
            p.fire_timer = random.uniform(0.8, 2.6)
        # never let a fresh level sit on top of the ball
        self.collide_planets(count_hits=False)

    def next_level(self):
        self.level += 1
        self.spawn_level()

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                if self.state == STATE_OVER:
                    if e.key in (pygame.K_SPACE, pygame.K_r):
                        self.new_game()
                    continue
                if e.key == pygame.K_SPACE:
                    self.reset()
                if e.key == pygame.K_n:
                    self.next_level()
                if e.key == pygame.K_r:
                    self.randomize_color()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.dragging = True
                self.fire(e.pos)
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.dragging = False
        return True

    def fire(self, target):
        """Shoot a bolt from the nose toward the cursor."""
        if self.fire_cd > 0:
            return
        self.fire_cd = FIRE_DELAY
        aim = pygame.Vector2(target) - self.ball.pos
        if aim.length() < 14:
            aim = self.ball.vel.copy() if self.ball.vel.length() > 1e-6 \
                else pygame.Vector2(1, 0)
        d = aim.normalize()
        self.bolts.append(Bolt(self.ball.pos + d * (BALL_R + 6), d * BOLT_SPEED,
                               self.ball.color))
        self.ball.set_speed(self.ball.vel.length() - 45.0)
        self.play(self.snd_shoot)

    def update_bolts(self, dt):
        keep = []
        for b in self.bolts:
            if not b.update(dt):
                continue
            struck = None
            for p in self.planets:
                if p.alive and (b.pos - p.pos).length() < p.radius + b.r:
                    struck = p
                    break
            if struck is None:
                keep.append(b)
            else:
                self.damage_planet(struck)
        self.bolts = keep

    def collide_planets(self, count_hits=True):
        for p in self.planets:
            if not p.alive:
                continue
            normal, depth = p.collide(self.ball.pos, BALL_R)
            if normal is None:
                continue
            self.ball.pos += normal * depth
            if count_hits and self.ball.vel.dot(normal) < 0:
                self.ball.vel = self.ball.vel - 2 * self.ball.vel.dot(normal) * normal
            if count_hits:
                self.damage_planet(p)
                self.ball.set_speed(self.ball.vel.length() + 18.0)

    def count_hits(self):
        """Hits the ship has made: rams plus bolt strikes (wall bounces excluded)."""
        return self.hits_dealt

    def damage_planet(self, planet):
        planet.hits += 1
        planet.flash = 0.12
        self.hits_dealt += 1
        broken_now = planet.hits >= planet.max_hits
        self.shake = min(12.0, self.shake + (9.0 if broken_now else 3.0))
        if not broken_now:
            self.play(self.snd_hit)
            return

        planet.alive = False
        self.broken += 1
        self.level_broken += 1
        self.score += 10 * planet.max_hits
        self.play(self.snd_break)
        if not any(p.alive for p in self.planets):
            self.banner = f"LEVEL {self.level} CLEARED"
            self.banner_time = 1.4
            self.level_delay = LEVEL_DELAY

    def update_shooters(self):
        for p in self.planets:
            if not (p.alive and p.shooter and p.fire_timer <= 0):
                continue
            p.fire_timer = p.interval * random.uniform(0.75, 1.25)
            self.meteors.extend(p.fire(self.ball.pos))
            self.play(self.snd_shoot)

    def check_meteors(self):
        if self.invuln > 0:
            return
        for m in self.meteors:
            if (m.pos - self.ball.pos).length() < m.r + BALL_R:
                self.lose_life()
                return

    def lose_life(self):
        self.lives -= 1
        self.shake = 16.0
        self.meteors.clear()
        self.reset()
        self.invuln = INVULN
        self.play(self.snd_hurt)
        if self.lives <= 0:
            self.state = STATE_OVER
            self.banner = "GAME OVER"
            self.banner_time = 99.0

    def update(self, dt, mouse):
        if self.state == STATE_OVER:
            self.shake = max(0.0, self.shake - SHAKE_DECAY * dt)
            return

        if self.dragging:
            target = pygame.Vector2(mouse)
            pull = (target - self.ball.pos) * DRAG_PULL
            if pull.length() > DRAG_MAX:
                pull = pull.normalize() * DRAG_MAX
            self.ball.vel = pull
            self.ball.pos.x = max(BALL_R, min(WIDTH - BALL_R, self.ball.pos.x))
            self.ball.pos.y = max(BALL_R, min(HEIGHT - BALL_R, self.ball.pos.y))

        if self.ball.update(dt, bouncing=not self.dragging) == "wall":
            self.bounces += 1
            self.play(self.snd_wall)
        if self.ball.vel.length() > 1.0:
            self.ship_heading = math.atan2(self.ball.vel.y, self.ball.vel.x)

        self.collide_planets(count_hits=not self.dragging)

        for p in self.planets:
            p.update(dt)
        self.update_shooters()
        self.meteors = [m for m in self.meteors if m.update(dt)]
        self.check_meteors()
        self.update_bolts(dt)

        if self.level_delay > 0:
            self.level_delay -= dt
            if self.level_delay <= 0:
                self.next_level()

        self.fire_cd = max(0.0, self.fire_cd - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.shake = max(0.0, self.shake - SHAKE_DECAY * dt)
        self.banner_time = max(0.0, self.banner_time - dt)

    def draw_world(self):
        self.world.fill(BG)
        self.world.blit(self.stars, (0, 0))
        pygame.draw.rect(self.world, WALL, pygame.Rect(0, 0, WIDTH, 3))

        for p in self.planets:
            if p.alive:
                p.draw(self.world)

        blink = self.invuln > 0 and int(self.invuln * 12) % 2 == 0
        cx, cy = int(self.ball.pos.x), int(self.ball.pos.y)
        if not blink:
            draw_ship(self.world, self.ball.pos, self.ship_heading,
                      self.ball.color, self.ball.vel.length())
        if self.invuln > 0:
            pygame.draw.circle(self.world, (255, 255, 255), (cx, cy), BALL_R + 9, 2)

        for b in self.bolts:
            b.draw(self.world)

        for m in self.meteors:
            m.draw(self.world)

    def draw(self):
        self.draw_world()
        ox = int(random.uniform(-self.shake, self.shake))
        oy = int(random.uniform(-self.shake, self.shake))
        self.screen.fill(BG)
        self.screen.blit(self.world, (ox, oy))
        for x, w in ((0, ox), (WIDTH + ox, -ox)):
            if w > 0:
                pygame.draw.rect(self.screen, BG, (x, 0, w, HEIGHT))
        for y, h in ((0, oy), (HEIGHT + oy, -oy)):
            if h > 0:
                pygame.draw.rect(self.screen, BG, (0, y, WIDTH, h))

        left = [f"LEVEL {self.level}", f"SPEED {int(self.ball.vel.length())}",
                f"HITS {self.count_hits()}"]
        for i, line in enumerate(left):
            surf = self.font.render(
                line, True,
                (220, 225, 235) if i == 0 else ((150, 200, 240) if i == 1 else (200, 215, 160)))
            self.screen.blit(surf, (16, 14 + i * 24))

        total = self.level_broken + sum(1 for p in self.planets if p.alive)
        right = [f"PLANETS {self.level_broken}/{total}", f"SCORE {self.score}"]
        for i, line in enumerate(right):
            surf = self.font.render(line, True, (235, 150, 150) if i else (240, 200, 120))
            self.screen.blit(surf, (WIDTH - surf.get_width() - 16, 14 + i * 24))

        for i in range(LIVES):
            filled = i < self.lives
            color = (235, 90, 90) if filled else (60, 60, 75)
            pygame.draw.circle(self.screen, color, (WIDTH - 22 - i * 22, 72), 8)

        if self.banner_time > 0:
            big = self.font_big.render(self.banner, True,
                                       (240, 110, 110) if self.state == STATE_OVER
                                       else (150, 235, 175))
            self.screen.blit(big, (WIDTH // 2 - big.get_width() // 2, HEIGHT // 2 - 60))

        if self.state == STATE_OVER:
            msg = "press SPACE to play again"
            surf = self.font.render(msg, True, (220, 225, 235))
            self.screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT // 2 + 6))
        elif self.bounces == 0 and self.broken == 0:
            hint = self.font.render("click to shoot    drag to steer",
                                    True, (150, 160, 185))
            self.screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT // 2 - 10))

        footer = "shoot: left click    steer: drag    next level: N    reset: space    color: R    quit: esc"
        surf2 = self.small.render(footer, True, (110, 120, 145))
        self.screen.blit(surf2, (WIDTH // 2 - surf2.get_width() // 2, HEIGHT - 40))

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            mouse = pygame.mouse.get_pos()
            if not self.handle_events():
                break
            self.update(dt, mouse)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()