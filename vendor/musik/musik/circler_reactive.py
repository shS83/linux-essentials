"""Circler Tetra scene logic and ModernGL renderer.

Standalone from Qt and Pygame: both frontends can share the same original
spiral, 3-D tetrahedron geometry, timed spawning and rotations.
"""
from __future__ import annotations

from dataclasses import dataclass
from array import array
import math
import random

import moderngl

SPAWN_INTERVAL = 0.3
BARS_PER_PALETTE = 4
BEATS_PER_BAR = 4  # 4/4: 4 bars = 16 detected quarter-note beats
PALETTE_BEATS = BARS_PER_PALETTE * BEATS_PER_BAR
BASS_KICK_MULTIPLIER = 1.8
BACKGROUND_SECONDS_PER_STEP = 12.0
BACKGROUND_COLORS = ((20, 20, 40), (40, 40, 20), (40, 20, 20))
INITIAL_PALETTE = ((255, 110, 0), (255, 20, 185))  # orange / magenta
NEON_PALETTES = (
    ((0, 240, 255), (160, 255, 20)),    # cyan / lime
    ((180, 65, 255), (255, 230, 45)),   # violet / yellow
    ((255, 60, 100), (10, 255, 205)),   # coral / turquoise
    ((255, 175, 30), (85, 120, 255)),   # amber / electric blue
    ((45, 255, 110), (255, 35, 220)),   # green / fuchsia
    ((255, 235, 75), (70, 155, 255)),   # lemon / azure
)

VERTEX_SHADER = """
#version 330
in vec3 in_position;
in vec3 in_normal;
uniform vec2 viewport_size;
uniform vec2 center;
uniform float size;
uniform vec3 rotation;
out vec3 normal;
void main() {
    vec3 c = cos(rotation);
    vec3 s = sin(rotation);
    mat3 rx = mat3(1, 0, 0, 0, c.x, s.x, 0, -s.x, c.x);
    mat3 ry = mat3(c.y, 0, -s.y, 0, 1, 0, s.y, 0, c.y);
    mat3 rz = mat3(c.z, s.z, 0, -s.z, c.z, 0, 0, 0, 1);
    mat3 model_rotation = rz * ry * rx;
    vec3 position = model_rotation * in_position * size;
    normal = model_rotation * in_normal;
    vec2 pixel = center + vec2(position.x, -position.y);
    gl_Position = vec4(
        2.0 * pixel.x / viewport_size.x - 1.0,
        1.0 - 2.0 * pixel.y / viewport_size.y,
        -position.z / 1000.0,
        1.0
    );
}
"""

FRAGMENT_SHADER = """
#version 330
in vec3 normal;
uniform vec3 color;
out vec4 frag_color;
void main() {
    vec3 n = normalize(normal);
    vec3 light = normalize(vec3(-0.5, 0.8, 1.0));
    float diffuse = max(dot(n, light), 0.0);
    vec3 halfway = normalize(light + vec3(0.0, 0.0, 1.0));
    float specular = pow(max(dot(n, halfway), 0.0), 32.0);
    frag_color = vec4(color * (0.25 + 0.75 * diffuse) + 0.2 * specular, 1.0);
}
"""

FLASH_VERTEX_SHADER = """
#version 330
in vec2 in_position;
void main() { gl_Position = vec4(in_position, 0.0, 1.0); }
"""
FLASH_FRAGMENT_SHADER = """
#version 330
uniform float flash_alpha;
out vec4 frag_color;
void main() { frag_color = vec4(1.0, 1.0, 1.0, flash_alpha); }
"""

# Black in the center, reaching the time-varying background color exactly at
# the window boundary in every direction. Use pixel coordinates, not UVs, so
# the well remains radially symmetric on rectangular and high-DPI viewports.
BACKGROUND_FRAGMENT_SHADER = """
#version 330
uniform vec2 viewport_size;
uniform vec3 edge_color;
out vec4 frag_color;
void main() {
    vec2 half_size = max(viewport_size * 0.5, vec2(1.0));
    vec2 delta = gl_FragCoord.xy - half_size;
    float distance_to_center = length(delta);
    vec2 direction = delta / max(distance_to_center, 0.00001);
    float distance_to_edge = min(
        half_size.x / max(abs(direction.x), 0.00001),
        half_size.y / max(abs(direction.y), 0.00001)
    );
    float radius = clamp(distance_to_center / distance_to_edge, 0.0, 1.0);
    // Black core and a gradual falloff that stays dark until the outer edges.
    float brightness = pow(smoothstep(0.07, 1.0, radius), 1.45);
    frag_color = vec4(edge_color * brightness, 1.0);
}
"""


def _lerp_color(first, second, amount):
    return tuple(int(round(a + (b - a) * amount)) for a, b in zip(first, second))


def _smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _vec_sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(a):
    length = math.sqrt(_dot(a, a))
    return tuple(x / length for x in a)


def tetrahedron_vertices():
    # Identical vertices, winding and face normals to the original Circler.
    vertices = tuple(_norm(p) for p in ((1, 1, 1), (1, -1, -1),
                                        (-1, 1, -1), (-1, -1, 1)))
    data = array("f")
    for indices in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)):
        a, b, c = (vertices[i] for i in indices)
        normal = _norm(_cross(_vec_sub(b, a), _vec_sub(c, a)))
        if _dot(normal, a) < 0:
            b, c = c, b
            normal = tuple(-x for x in normal)
        for vertex in (a, b, c):
            data.extend(vertex)
            data.extend(normal)
    return data.tobytes()


@dataclass
class Tetrahedron:
    color: tuple[int, int, int]
    size: float = 1.0
    max_size: float = 50.0
    size_speed: float = 6.0
    rotation: float = 0.0
    rotation_speed: float = math.radians(60.0)
    radius: float = 0.0
    angle: float = 0.0
    angular_speed: float = 2.0
    growth_speed: float = 20.0
    kick: float = 0.0

    def update(self, dt):
        self.size = min(self.max_size, self.size + self.size_speed * dt)
        self.rotation = (self.rotation + self.rotation_speed * dt) % (20 * math.tau)
        self.angle += self.angular_speed * dt
        self.radius += self.growth_speed * dt
        # Bass adds a temporary radial offset; original spiral growth is intact.
        self.kick *= math.exp(-dt * 7.5)

    def position(self, width, height):
        radial = self.radius + self.kick
        return (width / 2 + math.cos(self.angle) * radial,
                height / 2 + math.sin(self.angle) * radial)

    def is_visible(self, width, height):
        x, y = self.position(width, height)
        return -self.size < x < width + self.size and -self.size < y < height + self.size


class CirclerScene:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self.total_spawns = 0
        self.total_beats = 0
        self.palette_index = -1
        self.current_palette = INITIAL_PALETTE
        self.flash = 0.0
        self.last_beat_time = float("-inf")
        self.tetrahedra = [self._spawn()]

    def _spawn(self):
        # Different hues inside the pair; each retains its birth color for life.
        t = (math.sin(self.total_spawns * 1.517) + 1.0) * .5
        color = _lerp_color(*self.current_palette, t)
        self.total_spawns += 1
        return Tetrahedron(color)

    def beat(self):
        # Multiple callbacks for a single bass hit shouldn't count twice.
        if self.elapsed - self.last_beat_time < .20:
            return False
        self.last_beat_time = self.elapsed
        self.total_beats += 1
        self.flash = 1.0
        for tetra in self.tetrahedra:
            tetra.kick = min(80.0 * BASS_KICK_MULTIPLIER,
                             tetra.kick + BASS_KICK_MULTIPLIER * (16.0 + tetra.size * .38))
        if self.total_beats % PALETTE_BEATS == 0:
            candidate = self.rng.randrange(len(NEON_PALETTES))
            if len(NEON_PALETTES) > 1:
                while candidate == self.palette_index:
                    candidate = self.rng.randrange(len(NEON_PALETTES))
            self.palette_index = candidate
            self.current_palette = NEON_PALETTES[candidate]
        return True

    def update(self, dt, width, height):
        dt = max(0.0, min(float(dt), 0.10))
        self.elapsed += dt
        self.flash *= math.exp(-dt * 9.0)
        for tetra in self.tetrahedra:
            tetra.update(dt)
        self.tetrahedra = [t for t in self.tetrahedra if t.is_visible(width, height)]
        self.spawn_timer += dt
        while self.spawn_timer >= SPAWN_INTERVAL:
            self.spawn_timer -= SPAWN_INTERVAL
            self.tetrahedra.append(self._spawn())

    def background_color(self):
        segment = int(self.elapsed // BACKGROUND_SECONDS_PER_STEP)
        progress = (self.elapsed % BACKGROUND_SECONDS_PER_STEP) / BACKGROUND_SECONDS_PER_STEP
        return _lerp_color(BACKGROUND_COLORS[segment % 3],
                           BACKGROUND_COLORS[(segment + 1) % 3],
                           _smoothstep(progress))


class CirclerRenderer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.program = ctx.program(vertex_shader=VERTEX_SHADER,
                                   fragment_shader=FRAGMENT_SHADER)
        self.vertices = ctx.buffer(tetrahedron_vertices())
        self.vao = ctx.vertex_array(self.program, [(self.vertices, "3f 3f", "in_position", "in_normal")])
        self.background_program = ctx.program(vertex_shader=FLASH_VERTEX_SHADER,
                                              fragment_shader=BACKGROUND_FRAGMENT_SHADER)
        self.flash_program = ctx.program(vertex_shader=FLASH_VERTEX_SHADER,
                                         fragment_shader=FLASH_FRAGMENT_SHADER)
        self.flash_vertices = ctx.buffer(array("f", (-1., -1., 3., -1., -1., 3.)).tobytes())
        self.background_vao = ctx.vertex_array(self.background_program,
                                              [(self.flash_vertices, "2f", "in_position")])
        self.flash_vao = ctx.vertex_array(self.flash_program,
                                         [(self.flash_vertices, "2f", "in_position")])

    def draw(self, scene, width, height):
        if width <= 0 or height <= 0:
            return
        ctx = self.ctx
        ctx.viewport = (0, 0, width, height)
        r, g, b = scene.background_color()
        ctx.clear(0.0, 0.0, 0.0, 1.0, depth=1.)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        self.background_program["viewport_size"].value = (float(width), float(height))
        self.background_program["edge_color"].value = (r / 255., g / 255., b / 255.)
        self.background_vao.render(moderngl.TRIANGLES)
        ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.program["viewport_size"].value = (float(width), float(height))
        for t in scene.tetrahedra:
            self.program["center"].value = t.position(width, height)
            self.program["size"].value = t.size
            angle = t.rotation
            self.program["rotation"].value = (.55 * angle + .4, .7 * angle + .3, angle)
            self.program["color"].value = tuple(channel / 255. for channel in t.color)
            self.vao.render(moderngl.TRIANGLES)
        if scene.flash > .002:
            ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            self.flash_program["flash_alpha"].value = min(.14, scene.flash * .14)
            self.flash_vao.render(moderngl.TRIANGLES)
            ctx.disable(moderngl.BLEND)

    def release(self):
        self.background_vao.release()
        self.background_program.release()
        self.flash_vao.release()
        self.flash_vertices.release()
        self.flash_program.release()
        self.vao.release()
        self.vertices.release()
        self.program.release()
