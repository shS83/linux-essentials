"""Biolume predator/firefly simulation. Positions use viewport-height units."""
import numpy as np

FLY_COLORS = np.array(((.08, .84, 1.), (.18, .96, .32),
                       (1., .82, .12), (1., .18, .12)))


class Biolume:
    def __init__(self, aspect):
        self.rng = np.random.default_rng()
        angle = 2 * np.pi * (np.arange(8) + .3) / 8
        self.cells = np.column_stack((.34 * aspect * np.cos(angle), .36 * np.sin(angle),
                                      self.rng.uniform(.048, .078, 8), np.full(8, .13)))
        self.velocity = self.rng.uniform(-.08, .08, (8, 2))
        self.cooldown = np.zeros(8)
        self.merge_target = np.full(8, -1)
        self.merge_progress = np.zeros(8)
        self.merge_radius = np.zeros(8)
        self.merge_host_radius = np.zeros(8)
        self.base_colors = np.array([(.12,.47,1), (.55,.15,1), (.08,.72,.94), (.75,.18,.85)] * 2)
        self.pigment_weight = np.full(8, 7.)
        self.pigment_sum = self.base_colors * self.pigment_weight[:, None]
        self.colors = self.base_colors.copy()
        self.flies = np.column_stack((self.edges(48, aspect), self.rng.uniform(0, 2*np.pi, 48), np.ones(48)))
        self.flight = self.rng.uniform(-.04, .04, (48, 2))
        self.owner = np.full(48, -1)
        self.age = np.zeros(48)
        self.glows = np.zeros((16, 4))
        self.fragments = np.zeros((72, 4))
        self.burst_colors = np.zeros((2, 3))
        self.fragment_velocity = np.zeros((72, 2))
        self.fragment_radius = np.zeros(72)
        self.fragment_duration = np.ones(72)
        self.sparks = np.zeros((64, 4))
        self.spark_velocity = np.zeros((64, 2))
        self.spark_duration = np.ones(64)
        self.burst_count = 0
        self.pulse = 0.
        self.time = 0.

    def edges(self, count, aspect, margin=.07):
        points = self.rng.uniform(-.55, .55, (count, 2)) * [aspect, 1.]
        side = self.rng.integers(4, size=count)
        points[side < 2, 0] = np.where(side[side < 2] == 0, -1, 1) * (.5*aspect+margin)
        points[side >= 2, 1] = np.where(side[side >= 2] == 2, -1, 1) * (.5+margin)
        return points

    def glow(self, xy, color=4):
        slots = np.flatnonzero(self.glows[:, 3] <= 0)
        if len(slots):
            self.glows[slots[0]] = (*xy, color, 1)

    def burst(self, cell, aspect):
        group = next((g for g in range(2) if not (self.fragments[g*36:(g+1)*36, 3] > 0).any()), None)
        if group is None:
            return False
        center = self.cells[cell, :2].copy()
        self.burst_colors[group] = self.colors[cell]
        for i in range(36):
            slot = group*36+i
            angle = 2*np.pi*(i+self.rng.uniform(-.2, .2))/36
            direction = np.array((np.cos(angle), np.sin(angle)))
            radius = self.rng.uniform(.008, .016)
            position = center+direction*self.rng.uniform(0, .045)
            self.fragments[slot] = (*position, radius, 1.)
            self.fragment_velocity[slot] = direction*self.rng.uniform(.14, .31)
            self.fragment_radius[slot] = radius
            self.fragment_duration[slot] = self.rng.uniform(2.4, 3.8)
        free_sparks = np.flatnonzero(self.sparks[:, 3] <= 0)
        spark_count = min(24, len(free_sparks))
        for i, slot in enumerate(free_sparks[:spark_count]):
            angle = 2*np.pi*(i+self.rng.uniform(-.3, .3))/spark_count
            direction = np.array((np.cos(angle), np.sin(angle)))
            position = center+direction*self.rng.uniform(0, .025)
            self.sparks[slot] = (*position, self.rng.uniform(.0012, .0028), 1.)
            self.spark_velocity[slot] = direction*self.rng.uniform(.20, .55)
            self.spark_duration[slot] = self.rng.uniform(.65, 1.45)
        self.burst_count += 1
        self.glow(center)
        released = self.owner == cell
        self.owner[released] = -1
        self.age[released] = 0
        self.flies[released, 3] = 1
        self.cells[cell] = (*self.edges(1, aspect, .14)[0], self.rng.uniform(.045, .06), .13)
        self.velocity[cell] = self.rng.uniform(-.07, .07, 2)
        self.pigment_weight[cell] = 7.
        self.pigment_sum[cell] = self.base_colors[cell]*7.
        self.colors[cell] = self.base_colors[cell]
        self.cooldown[cell] = 2.
        return True

    def step(self, dt, aspect, bass, treble, pulse):
        dt = min(.035, dt)
        self.time += dt
        self.pulse = max(pulse, self.pulse*np.exp(-dt*6))
        self.glows[:, 3] = np.maximum(0, self.glows[:, 3] - dt*.75)
        active = self.fragments[:, 3] > 0
        self.fragments[active, :2] += self.fragment_velocity[active]*dt
        self.fragment_velocity[active] *= np.exp(-dt*.45)
        self.fragments[active, 3] = np.maximum(0, self.fragments[active, 3]-dt/self.fragment_duration[active])
        self.fragments[active, 2] = self.fragment_radius[active]*self.fragments[active, 3]
        active_sparks = self.sparks[:, 3] > 0
        self.sparks[active_sparks, :2] += self.spark_velocity[active_sparks]*dt
        self.spark_velocity[active_sparks] *= np.exp(-dt*1.1)
        self.sparks[active_sparks, 3] = np.maximum(0, self.sparks[active_sparks, 3]-dt/self.spark_duration[active_sparks])
        self.sparks[active_sparks, 2] *= np.exp(-dt*.6)
        cells, flies = self.cells, self.flies
        bounds = np.array([max(.001, aspect*.5-.035), .46])
        was_inside = (np.abs(cells[:, :2]) <= bounds).all(axis=1)
        free = self.owner < 0
        delta = flies[None, :, :2] - cells[:, None, :2]
        distance = np.linalg.norm(delta, axis=2)
        closest = np.argmin(np.where(free, distance, np.inf), axis=1)
        target = delta[np.arange(8), closest]
        target /= np.maximum(1e-8, np.linalg.norm(target, axis=1, keepdims=True))
        phase = self.time*.38 + np.arange(8)*2.39996
        waypoint = np.column_stack((.16*aspect*np.sin(phase), .15*np.cos(phase*1.13)))
        toward_middle = waypoint-cells[:, :2]
        toward_middle /= np.maximum(1e-8, np.linalg.norm(toward_middle, axis=1, keepdims=True))
        hunting = (free.any() & (distance[np.arange(8), closest] < .28))[:, None]
        target = np.where(hunting, target*.78+toward_middle*.22, toward_middle)
        target[~was_inside] = toward_middle[~was_inside]
        target /= np.maximum(1e-8, np.linalg.norm(target, axis=1, keepdims=True))
        wiggle = np.column_stack((np.sin(self.time*.91 + np.arange(8)*2.8),
                                  np.cos(self.time*.77 + np.arange(8)*1.9)))
        self.velocity += (target*(.14+.07*bass+.045*pulse) + wiggle*.028-self.velocity)*dt*1.7
        cells[:, :2] += self.velocity*dt
        for small in np.flatnonzero(self.merge_target >= 0):
            big = self.merge_target[small]
            self.merge_progress[small] = min(1., self.merge_progress[small]+dt/.65)
            ease = self.merge_progress[small]**2*(3-2*self.merge_progress[small])
            offset = cells[small, :2]-cells[big, :2]
            host_area = self.merge_host_radius[small]**2
            prey_area = self.merge_radius[small]**2
            pull = min(1., dt*(3+6*self.merge_progress[small]))
            cells[big, :2] += offset*pull*prey_area/(host_area+prey_area)
            cells[small, :2] -= offset*pull*host_area/(host_area+prey_area)
            cells[small, 2] = max(.002, self.merge_radius[small]*(1-ease))
            cells[big, 2] = min(.17, np.sqrt(self.merge_host_radius[small]**2 +
                                           .65*self.merge_radius[small]**2*ease))
            self.colors[big] = ((self.pigment_sum[big]+self.pigment_sum[small]*ease) /
                                (self.pigment_weight[big]+self.pigment_weight[small]*ease))
            if self.merge_progress[small] >= 1:
                self.pigment_sum[big] += self.pigment_sum[small]
                self.pigment_weight[big] += self.pigment_weight[small]
                cells[big, 3] = min(1.5, cells[big, 3]+.7*cells[small, 3])
                self.glow(cells[big, :2])
                cells[small] = (*self.edges(1, aspect, .14)[0], self.rng.uniform(.045, .065), .14)
                was_inside[small] = False
                self.pigment_weight[small] = 7.
                self.pigment_sum[small] = self.base_colors[small]*7.
                self.colors[small] = self.base_colors[small]
                self.velocity[small] = self.rng.uniform(-.07, .07, 2)
                self.cooldown[[big, small]] = [2.5, 3.]
                self.owner[self.owner == small] = big
                self.merge_target[small] = -1
        hit = was_inside[:, None] & (np.abs(cells[:, :2]) > bounds)
        self.velocity[hit] *= -1
        cells[was_inside, :2] = np.clip(cells[was_inside, :2], -bounds, bounds)
        cells[:, 2] = np.minimum(.18, cells[:, 2]+dt*(.0011+.0014*max(0, bass)))
        cells[:, 3] = np.maximum(.06, cells[:, 3]-dt*.025)
        self.cooldown = np.maximum(0, self.cooldown-dt)
        delta = flies[None, :, :2] - cells[:, None, :2]
        distance = np.linalg.norm(delta, axis=2)
        avoid = (delta*((distance < .30)/(distance**2+.009))[:, :, None]).sum(axis=0)
        heading = np.column_stack((np.cos(flies[:, 2]), np.sin(flies[:, 2])))
        desired = heading*.04 + avoid*.005
        desired /= np.maximum(1e-8, np.linalg.norm(desired, axis=1, keepdims=True))
        self.flight += (desired*(.075+.035*treble)-self.flight)*dt*3
        flies[free, :2] += self.flight[free]*dt
        flies[free, 2] += dt*.7*np.sin(self.time*2+np.flatnonzero(free)*1.71)
        nearest = distance.argmin(axis=0)
        caught = free & (distance.min(axis=0) < cells[nearest, 2]*.75)
        for i in np.flatnonzero(caught):
            c = nearest[i]
            self.owner[i] = c
            self.age[i] = 0
            cells[c, 2:] = np.minimum([.18, 1.5], cells[c, 2:]+[.0025, .16])
            self.pigment_sum[c] += FLY_COLORS[i % 4]
            self.pigment_weight[c] += 1
            self.colors[c] = self.pigment_sum[c]/self.pigment_weight[c]
            self.glow(flies[i, :2], i % 4)
        captive = self.owner >= 0
        self.age[captive] += dt
        host = cells[self.owner[captive]]
        flies[captive, 2] += dt*(4+4*treble)
        angle = flies[captive, 2]
        radius = np.maximum(.004, host[:, 2]*(.65-.55*self.age[captive]))
        flies[captive, :2] = host[:, :2] + radius[:, None]*np.column_stack((np.cos(angle), np.sin(angle)))
        flies[captive, 3] = -1
        respawn = (captive & (self.age > 1.25)) | (free & (np.abs(flies[:, :2]) > [aspect*.5+.17,.67]).any(axis=1))
        flies[respawn, :2] = self.edges(respawn.sum(), aspect)
        flies[respawn, 3] = 1
        self.owner[respawn] = -1
        for a,b in zip(*np.triu_indices(8,1)):
            if (self.cooldown[a] or self.cooldown[b] or self.merge_target[a] >= 0 or
                self.merge_target[b] >= 0 or a in self.merge_target or b in self.merge_target or
                np.linalg.norm(cells[a,:2]-cells[b,:2]) > .82*(cells[a,2]+cells[b,2])):
                continue
            big, small = (a,b) if cells[a,2]>=cells[b,2] else (b,a)
            self.merge_target[small] = big
            self.merge_progress[small] = 0
            self.merge_radius[small] = cells[small, 2]
            self.merge_host_radius[small] = cells[big, 2]
        for c in range(8):
            if (cells[c, 2] >= .13 and self.merge_target[c] < 0 and c not in self.merge_target and
                abs(cells[c, 0]) < aspect*.5-.18 and abs(cells[c, 1]) < .32):
                self.burst(c, aspect)

    def upload(self, program):
        for name, data in (("u_cells",self.cells), ("u_flies",self.flies),
                           ("u_cellColors",self.colors), ("u_glows",self.glows),
                           ("u_fragments",self.fragments), ("u_burstColors",self.burst_colors),
                           ("u_sparks",self.sparks)):
            program[name].write(data.astype("f4").tobytes())

