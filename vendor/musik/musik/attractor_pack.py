"""Music-reactive Clifford, De Jong, Lorenz and Aizawa from Attractor/attractorpack.py.

MusiK supplies decoded music levels; the standalone microphone/demo audio is not
needed. Simulation uses 60 Hz steps, while the switch timer uses visible wall time.
"""
import math

import numpy as np


NAMES = ('Clifford', 'De Jong', 'Lorenz', 'Aizawa')
SWITCH_SECONDS = 15.0
PALETTES = (
    ((1, 1, 1), (0, .33, .67)),
    ((1, 1, .5), (.80, .90, .30)),
    ((1, .7, .4), (0, .15, .20)),
    ((2, 1, 0), (.50, .20, .25)),
)
LIMITS = (10., 6., 150., 8.)


class AttractorPackScene:
    def __init__(self, count=250_000, seed=7, *, gpu=False):
        self.gpu = gpu
        self.generation = self.clear_generation = self.burst_generation = 0
        self.rng = np.random.default_rng(seed)
        self.count = max(1, count)
        self.current = 0
        self.bases = [[-1.4, 1.6, 1., .7], [1.4, -2.3, 2.4, -2.1]]
        if not gpu:
            self.x, self.y, self.z = self.seed(self.count)
            self.hist = np.zeros((1, 1), np.float32)
        self.levels = np.zeros(3)
        self.time = self.phase = self.bass = self.spin = self.spin_velocity = 0.
        self.pending = 1 / 60
        self.peak = 1e-3
        self.palette = 0
        self.paused = False
        self.hud_visible = False
        self.auto_switch = True
        self.switch_elapsed = 0.
        self.audio_enabled = True
        self.pointer = (0., 0.)
        self.parameters = self.params()

    @property
    def name(self):
        return NAMES[self.current]

    def seed(self, n):
        bounds = ((-15, 15), (-20, 20), (5, 40)) if self.current == 2 else (
            ((-.8, .8), (-.8, .8), (-.2, 1.2)) if self.current == 3 else
            ((-1, 1), (-1, 1), (0, 0)))
        return tuple(self.rng.uniform(lo, hi, n).astype(np.float32) for lo, hi in bounds)

    def reset(self):
        """Reset playback response without changing the user's mode or timer."""
        self.levels.fill(0)
        self.bass = self.spin_velocity = 0.
        self.clear_generation += 1
        if not self.gpu:
            self.hist.fill(0)
        self.peak = 1e-3

    def select(self, index):
        self.current = index % len(NAMES)
        self.generation += 1
        if not self.gpu:
            self.x, self.y, self.z = self.seed(self.count)
            self.hist *= .35
        self.peak = 1e-3
        self.pending = 1 / 60
        self.switch_elapsed = 0.
        self.parameters = self.params()

    def toggle_auto(self):
        self.auto_switch = not self.auto_switch
        self.switch_elapsed = 0.

    def advance_clock(self, dt):
        # Do not slow the 15 s timer down when rendering takes more than 50 ms.
        if self.auto_switch:
            elapsed = self.switch_elapsed + max(0., dt)
            switches = int(elapsed / SWITCH_SECONDS)
            if switches:
                self.select(self.current + switches)
            self.switch_elapsed = elapsed % SWITCH_SECONDS

    def toggle_audio(self):
        self.audio_enabled = not self.audio_enabled
        if not self.audio_enabled:
            self.levels.fill(0)
            self.bass = self.spin_velocity = 0.

    def beat(self, strength=1.):
        if self.audio_enabled:
            strength = float(np.clip(strength, 0, 1))
            self.bass = max(self.bass, strength)
            self.phase += .06 * strength
            self.spin_velocity = min(3., self.spin_velocity + .6 * strength)

    def burst(self):
        self.burst_generation += 1
        if self.gpu:
            return
        n = self.count // 3
        x, y, z = self.seed(n)
        self.x[:n], self.y[:n], self.z[:n] = x * 1.8, y * 1.8, z

    def randomize(self):
        if self.current == 0:
            self.bases[0] = self.rng.uniform([-2, 1.2, .5, .5], [-1.2, 2, 1.6, 1.6]).tolist()
        elif self.current == 1:
            self.bases[1] = (self.rng.choice([-1, 1], 4) * self.rng.uniform(1.2, 2.8, 4)).tolist()
        else:
            self.spin = self.rng.uniform(0, 2 * math.pi)

    def params(self):
        t, mid = self.time, float(self.levels[1])
        mx, my = self.pointer
        if self.current == 0:
            a, b, c, d = self.bases[0]
            return (a + .30*math.sin(t*.31) + .12*mid,
                    b + .25*math.sin(t*.23+1.3) - .10*mid,
                    c + .35*math.sin(t*.17+.4) + mx*.8,
                    d + .30*math.sin(t*.29+2.1) + my*.8)
        if self.current == 1:
            a, b, c, d = self.bases[1]
            return (a + .25*math.sin(t*.27) + .15*mid,
                    b + .25*math.sin(t*.21+1),
                    c + .20*math.sin(t*.33+2) + mx*.6,
                    d + .20*math.sin(t*.19+.5) + my*.6)
        if self.current == 2:
            return (10., 28 + 6*mid + mx*6, 8/3 + .3*math.sin(t*.2))
        return (.95 + .04*math.sin(t*.23), .70 + mx*.15, .60,
                3.5 + .3*math.sin(t*.17) + .5*mid, .25, .10)

    def step(self, drive):
        x, y, z = self.x, self.y, self.z
        p = self.parameters
        if self.current == 0:
            a, b, c, d = p
            x, y = np.sin(a*y) + c*np.cos(a*x), np.sin(b*x) + d*np.cos(b*y)
        elif self.current == 1:
            a, b, c, d = p
            x, y = np.sin(a*y) - np.cos(b*x), np.sin(c*x) - np.cos(d*y)
        else:
            dt = (.006 if self.current == 2 else .011) * drive
            for _ in range(2):
                if self.current == 2:
                    sig, rho, beta = p
                    dx, dy, dz = sig*(y-x), x*(rho-z)-y, x*y-beta*z
                else:
                    a, b, c, d, e, f = p
                    dx, dy = (z-b)*x-d*y, d*x+(z-b)*y
                    dz = c+a*z-z*z*z/3 - (x*x+y*y)*(1+e*z) + f*z*x*x*x
                x, y, z = x+dx*dt, y+dy*dt, z+dz*dt
        self.x, self.y, self.z = x, y, z
        self.repair_points()

    def repair_points(self):
        limit = LIMITS[self.current]
        valid = ((np.abs(self.x) < limit) & (np.abs(self.y) < limit) & (np.abs(self.z) < limit))
        if not valid.all():
            self.x[~valid], self.y[~valid], self.z[~valid] = self.seed(int((~valid).sum()))

    def project(self, w, h, bass):
        is3d = self.current >= 2
        angle = self.spin + (self.pointer[0]*3 if is3d else 0)
        ca, sa = math.cos(angle), math.sin(angle)
        x, y, z = self.x, self.y, self.z
        horizontal = x*ca-y*sa
        vertical = x*sa+y*ca
        zoom = min(w, h) / (5.4, 4.4, 62., 3.8)[self.current] * (1+.10*bass)
        weights = None
        if is3d:
            z = z - (25. if self.current == 2 else .45)
            tilt = .4+self.pointer[1]*.8
            ct, st = math.cos(tilt), math.sin(tilt)
            depth = vertical*ct + z*st
            vertical = -(z*ct-vertical*st)
            weights = np.clip(.8 + depth*(.02 if self.current == 2 else .25), .25, 1.6)
        return ((horizontal*zoom+w/2).astype(np.int32),
                (vertical*zoom+h/2).astype(np.int32), weights)

    def render(self, dt, width, height, energy=0., mid=0., treble=0.):
        if self.gpu:
            raise RuntimeError("GPU scenes must use AttractorPackRenderer")
        scale = min(1., 1100/max(1, width), 800/max(1, height))
        w, h = max(1, round(width*scale)), max(1, round(height*scale))
        if self.hist.shape != (h, w):
            self.hist = np.zeros((h, w), np.float32)
            self.peak = 1e-3
        steps = self.prepare_frame(dt, energy, mid, treble)
        bass, treble = self.frame_bass, float(self.levels[2])
        dt = self.frame_dt
        self.repair_points()
        for _ in range(steps):
            self.step(1+1.5*bass)
            n = max(1, int(self.count*(.005+treble*.02)))
            r = self.rng.integers(0, self.count, n)
            self.x[r], self.y[r], self.z[r] = self.seed(n)
            px, py, weights = self.project(w, h, bass)
            valid = (px >= 0) & (px < w) & (py >= 0) & (py < h)
            self.hist *= .86
            self.hist += np.bincount(py[valid]*w+px[valid],
                                    weights=None if weights is None else weights[valid],
                                    minlength=w*h).reshape(h, w)
        v = np.log1p(self.hist*.9*(1+.9*bass))
        self.peak = max(self.peak*math.exp(-dt*1.2), float(v.max()), 1e-3)
        indices = (np.clip(v/self.peak, 0, 1)*255).astype(np.uint8)
        frequency, offset = PALETTES[self.palette]
        ramp = np.linspace(0, 1, 256)[:, None]
        colors = (.5+.5*np.cos(2*np.pi*(ramp*frequency+offset+self.phase)))
        colors *= ramp**.75
        palette = (np.clip(colors, 0, 1)*255).astype(np.uint8)
        return np.ascontiguousarray(palette[indices])

    def prepare_frame(self, dt, energy=0., mid=0., treble=0.):
        """Constant-size controls only; particle simulation stays on the renderer."""
        self.advance_clock(dt)
        dt = min(.05, max(0., dt))
        target = np.clip([energy, mid, treble], 0, 1) if self.audio_enabled else np.zeros(3)
        self.levels += (target-self.levels)*(1-math.exp(-dt/.12))
        self.bass *= math.exp(-dt*5.5)
        bass = max(float(self.levels[0]), self.bass)
        treble = float(self.levels[2])
        self.spin_velocity *= math.exp(-dt*2.5)
        if not self.paused:
            self.time += dt
            self.spin += (.12*(.6 if self.current >= 2 else 1) + self.spin_velocity)*dt
        self.phase += dt*(.03+.25*treble)
        self.parameters = self.params()
        self.pending = min(.05, self.pending+dt)
        steps = int(self.pending / (1/60))
        self.pending -= steps / 60
        self.frame_bass = bass
        self.frame_dt = dt
        return steps
