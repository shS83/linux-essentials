"""Vectorized Fireworks simulation with the C++ player's GPU point sprites."""
from dataclasses import dataclass

import moderngl
import numpy as np


@dataclass
class Rocket:
    pos: np.ndarray
    velocity: np.ndarray
    color: np.ndarray
    gravity: float
    hover: float
    style: int
    finale: bool


class Fireworks:
    palette = np.array([(255,92,138),(255,179,71),(142,252,84),(88,211,255),
                        (196,139,255),(255,242,117),(255,122,64),(255,255,255),
                        (125,249,255),(255,209,249)]) / 255

    def __init__(self, ctx, folder):
        self.ctx = ctx
        self.program = ctx.program(vertex_shader=(folder/"fireworks.vert").read_text(),
                                   fragment_shader=(folder/"fireworks.frag").read_text())
        self.buffer = ctx.buffer(reserve=18020*9*4, dynamic=True)
        self.vao = ctx.vertex_array(self.program, [(self.buffer, "2f f f 3f f f",
            "a_pos","a_size","a_life","a_color","a_shape","a_angle")])
        self.rng = np.random.default_rng()
        self.reset()

    def reset(self):
        self.time = self.launches = 0
        self.delay = 1.
        self.rockets = []
        self.crackles = []
        self.comets = []
        # x,y, vx,vy, lifetime, initial lifetime, size, RGB, shape, angle, spin, drag, gravity.
        self.sparks = np.empty((0,15), dtype="f4")

    def emit(self, pos, velocity, life, size, color, shape=0, drag=.988, gravity=42):
        n = min(len(velocity), 18000-len(self.sparks))
        if n == 0:
            return
        data = np.empty((len(velocity),15), dtype="f4")
        data[:, :2], data[:, 2:4] = pos, velocity
        data[:,4] = data[:,5] = life
        data[:,6], data[:,7:10], data[:,10] = size,color,shape
        data[:,11] = self.rng.uniform(0,2*np.pi,len(data))
        data[:,12] = self.rng.uniform(-5.5,5.5,len(data))
        data[:,13], data[:,14] = drag,gravity
        self.sparks = np.concatenate((self.sparks,data[:n]))

    def launch(self,w,h):
        r = self.rng
        self.launches += 1
        finale = self.launches % 9 == 0
        high = r.random()<.42
        y = h+r.uniform(8,35)
        target = h*(r.uniform(.06,.19) if finale else r.uniform(.11,.33) if high else r.uniform(.35,.57))
        g = r.uniform(155,250)
        self.rockets.append(Rocket(np.array([r.uniform(.14,.86)*w,y]),
            np.array([r.uniform(-38,38),-np.sqrt(2*g*max(120,y-target))]),
            self.palette[r.integers(10)],g,r.uniform(.30,.60) if finale else r.uniform(.12,.48)*(r.random()<.28),
            r.integers(4),finale))

    def burst(self,rocket,scale,energy):
        crackles = self.rng.random() < .25
        if self.rng.random() < .26:
            pattern = self.rng.choice(("oval", "double ring", "flower", "comets"))
            # A genuine isotropic burst behind EVERY geometrical pattern.
            # Prevents the oval/flower from looking like an isolated wire frame.
            self.cloud_burst(rocket, scale, energy, density=.55)
            self.pattern_burst(rocket, scale, energy, pattern)
        else:
            self.cloud_burst(rocket, scale, energy)
        if crackles:
            self.queue_crackles(rocket, scale)

    def pattern_burst(self, rocket, scale, energy, pattern):
        r = self.rng
        speed = 310 * scale * (1 + .28 * energy)
        if pattern == "comets":
            # 6–12 huge comets with real time-ordered tails: the oldest
            # (near the origin) portions disappear first, head stays lit.
            count = int(r.integers(6, 13))
            angles = np.arange(count) * (2*np.pi/count) + r.uniform(0, 2*np.pi)
            velocity = np.column_stack((np.cos(angles), np.sin(angles)))
            velocity *= speed * r.uniform(.84, 1.15, (count, 1))
            # Extend the travel time: deceleration is gradual, not a hard stop.
            travel = 1.85
            t = np.linspace(0, travel, 150)
            paths = rocket.pos + velocity[:, None, :] * ((1-np.exp(-.85*t))/.85)[:, None]
            paths[:, :, 1] += 49 * scale * t**2
            self.comets.append((self.time, paths, rocket.color, scale, travel))
            return

        count = int(r.integers(66, 99))
        angles = np.arange(count) * (2*np.pi/count) + r.uniform(0, 2*np.pi)
        tilt = r.choice((-1, 1)) * r.uniform(.12, .42)
        flatten = r.uniform(.25, .47)
        radius = np.ones(count)
        if pattern == "double ring":
            # Interleave a second, smaller concentric ring.
            radius[::2] = r.uniform(.52, .69)
        elif pattern == "flower":
            radius = .72 + .28*np.cos(r.integers(4, 8)*angles)
            flatten = r.uniform(.72, .94)
        xy = np.column_stack((np.cos(angles), flatten*np.sin(angles)))
        rotate = np.array([[np.cos(tilt), np.sin(tilt)], [-np.sin(tilt), np.cos(tilt)]])
        velocity = (xy @ rotate) * (speed * radius * r.uniform(.985, 1.015, count))[:, None]
        self.emit(rocket.pos, velocity, r.uniform(1.9, 2.6, count),
                  scale*r.uniform(5, 8, count), rocket.color, shape=1, drag=.994, gravity=28*scale)

    def comet_points(self, dpr):
        frames = []
        # Head fades smoothly *while still travelling*, rather than blinking
        # out at the last cached path point. The tail fades oldest first.
        self.comets = [c for c in self.comets if self.time-c[0] < 4.6]
        for started, paths, color, scale, travel in self.comets:
            age = self.time - started
            progress = np.linspace(0.0, 1.0, paths.shape[1])
            born = progress * travel
            segment_age = age - born
            # Keep trailing luminous dust, but extinguish from origin onward.
            persistence = 1.62
            tail_light = np.clip((persistence-segment_age)/.90, 0.0, 1.0)
            # Long taper across the LAST part of travel, including the head.
            travel_fade = np.clip((travel+.10-born)/.58, 0.0, 1.0)
            visible = (segment_age >= 0) & (tail_light > 0) & (travel_fade > 0)
            if not np.any(visible):
                continue
            data = np.zeros((len(paths), visible.sum(), 9), dtype="f4")
            data[:, :, :2] = paths[:, visible] * dpr
            # Thicker comets: bigger colored, soft-edged sprite trail.
            data[:, :, 2] = (20 + 20*progress[visible]) * scale * dpr
            data[:, :, 3] = (.28 + .38*progress[visible]) * tail_light[visible] * travel_fade[visible]
            data[:, :, 4:7] = color
            if age < travel:
                # Actual moving tip, with a continuous falloff approaching apex.
                last = np.flatnonzero(visible)[-1]
                head_fade = np.clip((travel+.03-age)/.57, 0.0, 1.0)
                data[:, -1, 2] = (60 + 10*head_fade) * scale * dpr
                data[:, -1, 3] = .95 * head_fade
            frames.append(data.reshape(-1, 9))
        return frames

    def cloud_burst(self,rocket,scale,energy,density=1.0):
        r = self.rng
        base_n = r.integers(2300,2800) if rocket.finale else r.integers(1300,1700)
        n = max(1, int(base_n * density))
        choice = r.random(n)
        u = r.random(n)
        radius = np.select([choice<.035,choice<.31,choice<.83],
                           [.001+.11*u**1.3,.08+.48*np.sqrt(u),.36+.56*np.sqrt(u)],.80+.48*u)
        angle = r.uniform(0,2*np.pi,n)
        if rocket.style==1:
            radius *= r.uniform(.8,1.08,n)
        elif rocket.style==2:
            radius *= .9+.1*np.abs(np.sin(angle*5))
        elif rocket.style==3:
            angle += .13*np.sin(np.arange(n)*.12)
        velocity = np.column_stack((np.cos(angle),np.sin(angle)))*(340*scale*(1+.28*energy)*radius[:,None])
        life = r.uniform(2.1,3.8,n) if rocket.finale else r.uniform(1.45,3.,n)
        size = r.uniform(2.,5.8,n) if rocket.finale else np.where(np.arange(n)%7==0,r.uniform(2.3,4.5,n),r.uniform(.65,1.4,n))
        shape = np.where(np.arange(n)%4==0,2,0)
        color = np.tile(rocket.color,(n,1))
        if rocket.style==3 and not rocket.finale:
            color[::27],shape[::27],life[::27] = 1,3,r.uniform(3.5,5.3,len(life[::27]))
        self.emit(rocket.pos,velocity,life,size,color,shape,.991 if rocket.style==1 else .988,65 if rocket.style==1 else 42)
    def queue_crackles(self, rocket, scale):
        r = self.rng
        for a in r.uniform(0,2*np.pi,8):
            direction = np.array([np.cos(a),np.sin(a)])
            self.crackles.append([rocket.pos+direction*r.uniform(25,90)*scale,
                                  direction*r.uniform(75,150),r.uniform(.30,1.15),
                                  np.array(((1.,1.,1.),(1.,.22,.18),(1.,.82,.08),
                                            (.18,.48,1.),(.20,1.,.32))[r.integers(5)])])

    def debug_burst(self, number):
        """Trigger an immediate explosion for the debug control overlay."""
        w, h = getattr(self, '_viewport', (1280., 720.))
        scale = float(np.clip(min(w / 1280, h / 720), .8, 2.3))
        color = self.palette[self.rng.integers(len(self.palette))]
        rocket = Rocket(np.array([self.rng.uniform(.28, .72) * w,
                                   self.rng.uniform(.20, .45) * h]),
                        np.zeros(2), color, 200., 0., 0, number == 6)
        if number == 1:
            self.cloud_burst(rocket, scale, .5)
        elif number in (2, 3, 4, 5):
            self.cloud_burst(rocket, scale, .5, density=.55)
            self.pattern_burst(rocket, scale, .5,
                               {2:'oval',3:'double ring',4:'flower',5:'comets'}[number])
        elif number == 6:
            self.cloud_burst(rocket, scale, 1.)
        elif number == 7:
            self.cloud_burst(rocket, scale, .5, density=.38)
            self.queue_crackles(rocket, scale)
        elif number == 8:
            self.pattern_burst(rocket, scale, .6, 'comets')
        elif number == 9:
            self.cloud_burst(rocket, scale, .75)
            self.queue_crackles(rocket, scale)
        else:
            return False
        return True

    def draw(self, dt, width, height, dpr, energy):
        self._viewport = (width, height)
        r = self.rng
        self.time += dt
        self.delay -= dt
        if self.delay<=0:
            self.launch(width,height)
            self.delay = r.uniform(2.8,4.7)
        for rocket in self.rockets[:]:
            if rocket.velocity[1]>=-12:
                rocket.hover -= dt
                if rocket.hover<=0:
                    self.burst(rocket,np.clip(min(width/1280,height/720),.8,2.3),energy)
                    self.rockets = [x for x in self.rockets if x is not rocket]
                continue
            previous = rocket.pos.copy()
            rocket.pos += rocket.velocity*dt
            rocket.velocity[1] += rocket.gravity*dt
            count = 5 if rocket.finale else 4
            self.emit(np.linspace(previous,rocket.pos,count),r.uniform([-13,8],[13,38],(count,2)),
                      r.uniform(.48,1.35,count),r.uniform(.7,2.3,count),rocket.color,drag=.96,gravity=35)
        pending = []
        for pos,velocity,delay,color in self.crackles:
            pos += velocity*dt
            if delay>dt:
                pending.append([pos,velocity*.97**(dt*60),delay-dt,color])
            else:
                n = r.integers(45,80)
                angle = r.uniform(0,2*np.pi,n)
                colors = np.tile(color,(n,1))
                # Preserve the selected color for the whole secondary burst.
                # White is one of the five permitted colors, not mandatory.
                # Sparkle aftermath: white pinpoints linger for several seconds.
                # Preserve the sharp random crackle gate in the GLSL shader.
                life = r.uniform(.85, 1.6, n)
                white = np.arange(n) % 3 == 0
                life[white] = r.uniform(2.1, 3.5, np.count_nonzero(white))
                shapes = np.where(white, 3, 2)
                self.emit(pos,np.column_stack((np.cos(angle),np.sin(angle)))*r.uniform(35,160,(n,1)),
                          life,r.uniform(.8,1.7,n),colors,shape=shapes,drag=.95,gravity=35)
        self.crackles = pending
        s = self.sparks[self.sparks[:,4]>dt]
        self.sparks = s
        s[:,4] -= dt
        s[:,:2] += dt*s[:,2:4]
        s[:,2:4] *= s[:,13:14]**(dt*60)
        s[:,3] += dt*s[:,14]
        s[:,11] += dt*s[:,12]
        points = np.empty((len(s)+len(self.rockets),9),dtype="f4")
        sparks = points[:len(s)]
        sparks[:,:2] = s[:,:2]*dpr
        sparks[:,2] = dpr*np.where(s[:,10]==2,1.5,np.where(s[:,10]==3,np.clip(s[:,6]*7.5,5,19),np.clip(s[:,6]*5,2,22)))
        large = s[:,10] == 1
        sparks[large,2] = dpr*np.clip(s[large,6]*6, 24, 84)
        sparks[:,3],sparks[:,4:7],sparks[:,7:9] = s[:,4]/s[:,5],s[:,7:10],s[:,10:12]
        for i,rocket in enumerate(self.rockets,len(s)):
            points[i] = (* (rocket.pos*dpr),28*dpr,1,*rocket.color,0,0)
        self.ctx.clear(.015,.008,.035,1.)
        if self.comets:
            points = np.concatenate([points, *self.comet_points(dpr)])
        if len(points):
            self.ctx.enable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            self.ctx.blend_func = moderngl.ONE,moderngl.ONE
            self.program["u_resolution"].value = (round(width*dpr),round(height*dpr))
            self.program["u_time"].value = self.time
            if points.nbytes > self.buffer.size:
                self.buffer.orphan(points.nbytes * 2)
            self.buffer.write(points)
            self.vao.render(moderngl.POINTS,vertices=len(points))
            self.ctx.disable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)

