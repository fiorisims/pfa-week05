"""Ball Bounce - a breakout-style paddle game built with pygame.

Controls:
    Mouse move / Left+Right arrows  move paddle
    Space                          launch ball / start new life
    R                              restart game
    Esc                            quit
"""

import math
import random
import sys
from array import array

import pygame

WIDTH, HEIGHT = 800, 600
FPS = 60

PADDLE_W, PADDLE_H = 110, 14
BALL_R = 9
BRICK_W, BRICK_H, BRICK_GAP = 76, 26, 8

ROW_COLORS = [
    (220, 70, 70),
    (240, 140, 60),
    (240, 210, 70),
    (110, 200, 110),
    (90, 160, 230),
]

STATE_READY = "ready"
STATE_PLAY = "play"
STATE_DEAD = "dead"
STATE_OVER = "over"
STATE_WIN = "win"


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


class Paddle:
    def __init__(self):
        self.w = PADDLE_W
        self.h = PADDLE_H
        self.rect = pygame.Rect(0, 0, self.w, self.h)
        self.rect.midbottom = (WIDTH // 2, HEIGHT - 24)
        self.speed = 640.0
        self.target_x = float(self.rect.centerx)

    def update(self, dt, keys):
        if keys[pygame.K_LEFT]:
            self.target_x -= self.speed * dt
        if keys[pygame.K_RIGHT]:
            self.target_x += self.speed * dt

        half = self.w / 2
        self.target_x = max(half, min(WIDTH - half, self.target_x))
        self.rect.centerx = int(self.target_x)

    def follow_mouse(self, mx):
        self.target_x = mx


class Ball:
    def __init__(self):
        self.r = BALL_R
        self.rect = pygame.Rect(0, 0, self.r * 2, self.r * 2)
        self.reset()

    def reset(self, paddle=None, launch=True):
        cx = paddle.rect.centerx if paddle is not None else WIDTH // 2
        self.rect.center = (cx, HEIGHT - PADDLE_H - 24 - self.r - 2)
        angle = math.radians(random.uniform(-62, -118))
        speed = 330.0
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
        self.launched = launch
        if not launch:
            self.vel = pygame.Vector2(0, 0)

    def speed_up(self, amount=12.0, max_speed=780.0):
        if self.vel.length() < max_speed:
            self.vel = self.vel.normalize() * (self.vel.length() + amount)

    def update(self, dt):
        self.rect.x += self.vel.x * dt
        self.rect.y += self.vel.y * dt

        if self.rect.left <= 0:
            self.rect.left = 0
            self.vel.x = abs(self.vel.x)
            return "wall"
        if self.rect.right >= WIDTH:
            self.rect.right = WIDTH
            self.vel.x = -abs(self.vel.x)
            return "wall"
        if self.rect.top <= 0:
            self.rect.top = 0
            self.vel.y = abs(self.vel.y)
            return "wall"
        return None


class Brick:
    def __init__(self, col, row):
        self.rect = pygame.Rect(0, 0, BRICK_W, BRICK_H)
        self.color = ROW_COLORS[row % len(ROW_COLORS)]
        self.alive = True


class Particle:
    def __init__(self, x, y, color):
        self.pos = pygame.Vector2(x, y)
        ang = random.uniform(0, math.tau)
        spd = random.uniform(60, 260)
        self.vel = pygame.Vector2(math.cos(ang), math.sin(ang)) * spd
        self.color = color
        self.life = random.uniform(0.25, 0.6)

    def update(self, dt):
        self.vel.y += 900 * dt
        self.pos += self.vel * dt
        self.life -= dt
        return self.life > 0


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Ball Bounce")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("consolas", 52, bold=True)
        self.font = pygame.font.SysFont("consolas", 20)
        self.small = pygame.font.SysFont("consolas", 16)

        pygame.mixer.pre_init(44100, -16, 1, 512)
        try:
            pygame.mixer.init()
            self.snd_brick = make_beep(880, 70)
            self.snd_paddle = make_beep(440, 50)
            self.snd_wall = make_beep(300, 35, 0.15)
            self.snd_death = make_beep(160, 320, 0.3)
        except pygame.error:
            self.snd_brick = self.snd_paddle = self.snd_wall = self.snd_death = None

        self.paddle = Paddle()
        self.ball = Ball()
        self.particles = []
        self.flash = 0.0
        self.state = STATE_READY
        self.reset_game()

    def reset_game(self):
        self.score = 0
        self.lives = 3
        self.level = 1
        self.rows = 4
        self.cols = 10
        self.ball_speed = 330.0
        self.build_level()
        self.state = STATE_READY

    def build_level(self):
        self.bricks = []
        top = 70
        margin = (WIDTH - (self.cols * (BRICK_W + BRICK_GAP) - BRICK_GAP)) / 2
        for row in range(self.rows):
            for col in range(self.cols):
                b = Brick(col, row)
                b.rect.x = margin + col * (BRICK_W + BRICK_GAP)
                b.rect.y = top + row * (BRICK_H + BRICK_GAP)
                self.bricks.append(b)

    def play(self, snd):
        if snd is not None:
            snd.play()

    def next_level(self):
        self.level += 1
        self.rows = min(4 + self.level, 7)
        self.cols = 10
        self.ball_speed = min(330.0 + (self.level - 1) * 22, 520.0)
        self.build_level()
        self.state = STATE_READY

    def launch(self):
        if self.state == STATE_READY:
            self.ball.reset(self.paddle, launch=True)
            self.state = STATE_PLAY
        elif self.state == STATE_DEAD:
            self.lives -= 1
            if self.lives <= 0:
                self.state = STATE_OVER
            else:
                self.ball.reset(self.paddle, launch=True)
                self.state = STATE_PLAY
        elif self.state == STATE_OVER or self.state == STATE_WIN:
            self.reset_game()

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                if e.key == pygame.K_SPACE:
                    self.launch()
                if e.key == pygame.K_r:
                    self.reset_game()
            if e.type == pygame.MOUSEMOTION:
                self.paddle.follow_mouse(e.pos[0])
        return True

    def collide_bricks(self):
        for b in self.bricks:
            if not b.alive or not self.ball.rect.colliderect(b.rect):
                continue
            b.alive = False
            self.score += 10
            self.flash = 0.12
            self.play(self.snd_brick)
            self.ball.speed_up(4.0)

            for _ in range(10):
                self.particles.append(
                    Particle(b.rect.centerx, b.rect.centery, b.color)
                )

            overlap_x = min(self.ball.rect.right - b.rect.left,
                            b.rect.right - self.ball.rect.left)
            overlap_y = min(self.ball.rect.bottom - b.rect.top,
                            b.rect.bottom - self.ball.rect.top)
            if overlap_x < overlap_y:
                self.ball.vel.x = -self.ball.vel.x
            else:
                self.ball.vel.y = -self.ball.vel.y
            break

        if not any(b.alive for b in self.bricks):
            if self.level >= 3:
                self.state = STATE_WIN
            else:
                self.next_level()

    def collide_paddle(self):
        if not self.ball.vel.y > 0:
            return
        if not self.ball.rect.colliderect(self.paddle.rect):
            return

        self.ball.rect.bottom = self.paddle.rect.top
        self.play(self.snd_paddle)
        self.ball.speed_up(6.0)

        rel = (self.ball.rect.centerx - self.paddle.rect.centerx) / (self.paddle.w / 2)
        rel = max(-1.0, min(1.0, rel))
        angle = math.radians(-90 + rel * 62)
        speed = self.ball.vel.length()
        self.ball.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed

    def update(self, dt, keys):
        self.paddle.update(dt, keys)

        if self.state == STATE_READY:
            self.ball.rect.centerx = self.paddle.rect.centerx
        elif self.state == STATE_PLAY:
            hit = self.ball.update(dt)
            if hit == "wall":
                self.play(self.snd_wall)
            self.collide_paddle()
            self.collide_bricks()

            if self.ball.rect.top > HEIGHT:
                self.play(self.snd_death)
                self.state = STATE_DEAD

        self.particles = [p for p in self.particles if p.update(dt)]
        self.flash = max(0.0, self.flash - dt)

    def draw_ball(self):
        cx, cy = self.ball.rect.center
        if self.state == STATE_READY or self.state == STATE_DEAD:
            pygame.draw.circle(self.screen, (150, 155, 170), (cx, cy + 18), self.ball.r)
        pygame.draw.circle(self.screen, (250, 250, 255), (cx, cy), self.ball.r)
        pygame.draw.circle(self.screen, (150, 200, 250), (cx - 3, cy - 3),
                           max(2, self.ball.r // 3))

    def draw(self):
        self.screen.fill((18, 20, 30))

        glow = pygame.Rect(0, 0, WIDTH, 3)
        pygame.draw.rect(self.screen, (70, 90, 140), glow)

        for b in self.bricks:
            if not b.alive:
                continue
            r = b.rect.inflate(-4, -4)
            pygame.draw.rect(self.screen, b.color, r, border_radius=4)
            shade = tuple(max(0, c - 55) for c in b.color)
            pygame.draw.rect(self.screen, shade, r, width=2, border_radius=4)

        if self.flash > 0:
            a = int(120 * (self.flash / 0.12))
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, a))
            self.screen.blit(overlay, (0, 0))

        for p in self.particles:
            fade = max(0.15, p.life / 0.6)
            pygame.draw.circle(self.screen, p.color,
                               (int(p.pos.x), int(p.pos.y)),
                               max(1, int(4 * fade)))

        p = self.paddle.rect
        pygame.draw.rect(self.screen, (40, 48, 70), p.inflate(6, 6), border_radius=8)
        pygame.draw.rect(self.screen, (230, 235, 245), p, border_radius=7)

        self.draw_ball()

        hud = self.font.render(f"SCORE {self.score}", True, (220, 225, 235))
        self.screen.blit(hud, (16, 14))
        lvl = self.font.render(f"LEVEL {self.level}/3", True, (170, 185, 210))
        self.screen.blit(lvl, (16, 40))
        lives = self.font.render("LIVES " + "*" * max(0, self.lives), True, (230, 120, 120))
        self.screen.blit(lives, (WIDTH - lives.get_width() - 16, 14))

        if self.state == STATE_READY:
            self.center_text("PRESS SPACE TO LAUNCH", self.font, (235, 238, 245))
        elif self.state == STATE_DEAD:
            self.center_text("MISSED - SPACE TO CONTINUE", self.font, (235, 150, 150))
        elif self.state == STATE_OVER:
            self.center_text("GAME OVER", self.font_big, (240, 110, 110))
            self.center_text("SPACE or R to play again", self.font, (220, 225, 235),
                             offset=48)
        elif self.state == STATE_WIN:
            self.center_text("YOU WIN!", self.font_big, (140, 230, 160))
            self.center_text("SPACE or R to play again", self.font, (220, 225, 235),
                             offset=48)

        self.center_text("move: mouse / arrows    launch: space    restart: R    quit: esc",
                         self.small, (110, 120, 145), offset=HEIGHT // 2 - 20)

    def center_text(self, msg, font, color, offset=0):
        surf = font.render(msg, True, color)
        self.screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2,
                                HEIGHT // 2 - 40 + offset))

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            keys = pygame.key.get_pressed()
            if not self.handle_events():
                break
            self.update(dt, keys)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
