"""Golden Torus v2.2 — sharp 144-tooth audio spectrum on mirror-chrome torus.

OpenGL 3.3 / ModernGL renderer. 48 live FFT bands are interpolated to a
4608-sample periodic 1D signal stored in a single-row float texture. Audio
ONLY affects inner size and the outer ring's outward-facing silhouette.
"""

from __future__ import annotations

from array import array
import math

import moderngl
import numpy as np

from .golden_torus_spectrum import PROFILE_SAMPLES, SPECTRUM_BANDS, ring_profile


# Geometry and visual tuning. All measurements are in world units.
INNER_MAJOR_RADIUS = 1.07
INNER_TUBE_RADIUS = 0.53
INNER_SCALE = 0.90
BASS_PULSE = 0.14

OUTER_MAJOR_RADIUS = 1.92
OUTER_TUBE_RADIUS = 0.11
OUTER_DISPLACE = 0.78  # tall, sharply tapered teeth; outward ONLY
RAINBOW_SPEED = 0.055  # Hue cycles per second.

# The ring can tilt in any direction without cutting through the floor.
FLOOR_Y = -3.18  # below the tip of even the tallest outer tooth
CENTER_Y = 0.18

# Maximum inner radius, including the strongest beat; and minimum outer radius.
INNER_ENVELOPE = (INNER_MAJOR_RADIUS + INNER_TUBE_RADIUS) * INNER_SCALE * (1.0 + BASS_PULSE)
OUTER_CLEARANCE = OUTER_MAJOR_RADIUS - OUTER_TUBE_RADIUS - INNER_ENVELOPE
assert OUTER_CLEARANCE > 0.12, "The inner and outer toruses must never intersect"
assert CENTER_Y - (OUTER_MAJOR_RADIUS + OUTER_TUBE_RADIUS + OUTER_DISPLACE) > FLOOR_Y + 0.12, "Outer torus may collide with the floor"

VERTEX_SHADER = r"""
#version 330 core
in vec3 in_position;
in vec3 in_normal;
in vec2 in_params;  // x = ring phase [0,1], y = tube angle [0,2*pi]

uniform float u_time;
uniform float u_pulse;
uniform float u_aspect;
uniform int u_object;  // 0 = inner, 1 = checker floor, 2 = spectrum outer
uniform int u_mirror;
uniform sampler2D u_spectrum; // periodic 1D profile stored in a 4608x1 row texture
uniform float u_outer_major;
uniform float u_outer_tube;
uniform float u_displace;
uniform float u_inner_scale;

out vec3 v_position;
out vec3 v_normal;
out float v_phase;

const float PI = 3.141592653589793;
const float FLOOR_Y = -3.18;
const vec3 CAMERA = vec3(0.0, 2.80, 9.3);
const vec3 TARGET = vec3(0.0, -0.30, 0.0);

mat3 rotate_x(float a) {
	return mat3(1., 0., 0., 0., cos(a), sin(a), 0., -sin(a), cos(a));
}
mat3 rotate_y(float a) {
	return mat3(cos(a), 0., -sin(a), 0., 1., 0., sin(a), 0., cos(a));
}
mat3 rotate_z(float a) {
	return mat3(cos(a), sin(a), 0., -sin(a), cos(a), 0., 0., 0., 1.);
}

// FFT frequency-band values wrap exactly around the full ring.
float spectrum_level(float phase) {
	return clamp(textureLod(u_spectrum, vec2(phase, 0.5), 0.0).r, 0.0, 1.0);
}

// The INNER edge and top/bottom of the thin tube remain smooth; only its
// OUTER side grows into sculpted frequency-spectrum peaks.
vec3 spectral_ring_position(float phase, float tube_angle) {
	float u = phase * (2.0 * PI);
	float cv = cos(tube_angle);
	float sv = sin(tube_angle);
	float facing = max(cv, 0.0);
	float falloff = facing * facing * facing * facing;
	float displacement = u_displace * spectrum_level(phase) * falloff;
	float rho = u_outer_major + u_outer_tube * cv + displacement;
	return vec3(rho * cos(u), u_outer_tube * sv, rho * sin(u));
}

void main() {
	vec3 position = in_position;
	vec3 normal = in_normal;
	v_phase = in_params.x;

	if (u_object == 0) {
		// Preserve the ChromeGold v1.1 shape and its bass-only size pulse.
		float ax = 0.50 + u_time * 0.3625;
		float ay = 0.22 + u_time * 0.4625;
		float az = 0.09 * sin(u_time * 0.2875);
		mat3 rotation = rotate_z(az) * rotate_y(ay) * rotate_x(ax);
		position = rotation * in_position * (u_inner_scale * (1.0 + u_pulse));
		normal = rotation * in_normal;
		position.y += 0.18;
	} else if (u_object == 2) {
		float phase = in_params.x;
		float v = in_params.y;
		position = spectral_ring_position(phase, v);

		// Finite difference normals follow the *actual* deformed surface.
		// This also keeps checkerboard/environment reflections chrome-like.
		const float du = 1.0 / 4608.0;
		const float dv = 0.010;
		vec3 tangent_u = spectral_ring_position(phase + du, v)
		                - spectral_ring_position(phase - du, v);
		vec3 tangent_v = spectral_ring_position(phase, v + dv)
		                - spectral_ring_position(phase, v - dv);
		normal = normalize(cross(tangent_v, tangent_u));

		// 25% faster than v2, rotation is independent of spectrum strength.
		float ax = 0.88 + 0.25 * sin(u_time * 0.225);
		float ay = 0.55 + u_time * 0.525;
		float az = 0.18 + 0.20 * sin(u_time * 0.325);
		mat3 rotation = rotate_z(az) * rotate_y(ay) * rotate_x(ax);
		position = rotation * position;
		normal = rotation * normal;
		position.y += 0.18;
	}

	if (u_mirror != 0 && u_object != 1) {
		position.y = 2.0 * FLOOR_Y - position.y;
		normal.y = -normal.y;
	}

	v_position = position;
	v_normal = normalize(normal);

	vec3 forward = normalize(TARGET - CAMERA);
	vec3 right = normalize(cross(forward, vec3(0., 1., 0.)));
	vec3 up = cross(right, forward);
	vec3 relative = position - CAMERA;
	float depth = dot(relative, forward);
	float focal = 1.0 / tan(radians(48.0) * 0.5);
	const float near = 0.1;
	const float far = 75.0;
	gl_Position = vec4(
		dot(relative, right) * focal / max(u_aspect, 0.1),
		dot(relative, up) * focal,
		((far + near) / (far - near)) * depth - (2. * far * near) / (far - near),
		depth
	);
}
"""

FRAGMENT_SHADER = r"""
#version 330 core
in vec3 v_position;
in vec3 v_normal;
in float v_phase;
out vec4 frag_color;

uniform int u_object;
uniform int u_mirror;
uniform float u_time;
uniform float u_rainbow_speed;

const float FLOOR_Y = -3.18;
const vec3 CAMERA = vec3(0.0, 2.80, 9.3);
const vec3 BACKGROUND = vec3(0.012, 0.014, 0.029);
const vec3 GOLD_FILTER = vec3(1.00, 0.87, 0.47);  // same ChromeGold v1.1
const vec3 TILE_RED = vec3(0.87, 0.020, 0.048);
const vec3 TILE_WHITE = vec3(0.94, 0.94, 0.92);

vec3 checker(vec2 xz) {
	vec2 uv = xz / 0.78;
	vec2 cells = floor(uv);
	float group = mod(cells.x + cells.y + 6000.0, 3.0);
	vec3 square = mix(TILE_RED, TILE_WHITE, step(0.5, group));
	vec3 average_square = (TILE_RED + 2.0 * TILE_WHITE) / 3.0;
	vec2 footprint_xy = fwidth(uv);
	float footprint = max(footprint_xy.x, footprint_xy.y);
	float clarity = 1.0 - smoothstep(0.12, 0.85, footprint);
	vec3 color = mix(average_square, square, clarity);
	vec2 f = fract(uv);
	float edge = min(min(f.x, f.y), min(1.0 - f.x, 1.0 - f.y));
	color *= 1.0 - clarity * 0.09 * (1.0 - smoothstep(0.0, 0.025, edge));
	return color;
}

vec3 studio_environment(vec3 r) {
	float h = clamp(0.50 + 0.5 * r.y, 0.0, 1.0);
	vec3 env = mix(vec3(0.012, 0.014, 0.025), vec3(0.044, 0.052, 0.076), h);
	env += vec3(0.24, 0.27, 0.32) * exp(-abs(r.y) * 8.0);
	env += vec3(1.85, 1.82, 1.65) * pow(max(dot(r, normalize(vec3(-1.3, 1.8, 1.0))), 0.0), 22.0);
	env += vec3(0.70, 0.83, 1.05) * pow(max(dot(r, normalize(vec3(1.5, 0.7, 0.2))), 0.0), 36.0);
	env += vec3(1.10, 1.05, 0.93) * smoothstep(0.982, 0.998, dot(r, normalize(vec3(0.2, 1.0, -0.8))));
	return env;
}

vec3 hsv_to_rgb(float hue) {
	vec3 p = abs(fract(vec3(hue, hue + 2.0 / 3.0, hue + 1.0 / 3.0)) * 6.0 - 3.0);
	return clamp(p - 1.0, 0.0, 1.0);
}

void main() {
	vec3 p = v_position;
	vec3 n = normalize(v_normal);
	vec3 view_direction = normalize(CAMERA - p);

	if (u_object == 1) {
		vec3 squares = checker(p.xz);
		float distance_fade = exp(-0.030 * length(p.xz));
		float light = 0.78 + 0.18 * clamp(1.0 - length(p.xz) / 20.0, 0.0, 1.0);
		float shadow = 1.0 - 0.20 * exp(-0.42 * dot(p.xz, p.xz));
		vec3 color = mix(BACKGROUND, squares * light * shadow, distance_fade);
		float near_reflection = exp(-0.21 * dot(p.xz, p.xz));
		frag_color = vec4(color, mix(1.0, 0.69, near_reflection));
		return;
	}

	// ChromeSphere-style environment: polished metal instead of diffuse paint.
	vec3 r = reflect(-view_direction, n);
	vec3 environment = studio_environment(r);
	float denom = max(abs(r.y), 0.018);
	float hit_distance = abs(FLOOR_Y - p.y) / denom;
	vec2 hit = p.xz + hit_distance * r.xz;
	vec3 reflected_tiles = checker(hit);
	if (r.y < -0.018 && p.y > FLOOR_Y && hit_distance < 85.0) {
		float visibility = 1.0 - smoothstep(12.0, 55.0, hit_distance);
		environment = mix(environment, reflected_tiles * 0.71, 0.90 * visibility);
	}

	float ndv = clamp(dot(n, view_direction), 0.0, 1.0);
	float fresnel = pow(1.0 - ndv, 5.0);
	vec3 filter_color = GOLD_FILTER;
	if (u_object == 2) {
		// A continuously shifting spectral rainbow, reflected metal rather
		// than a rainbow painted onto a matte object. White glints survive.
		// Exactly ONE whole HSV turn around ring: hue(phase=0) == hue(phase=1).
		float hue = fract(u_time * u_rainbow_speed + v_phase);
		vec3 rainbow = hsv_to_rgb(hue);
		filter_color = mix(vec3(0.74), rainbow, 0.75);
	}
	vec3 color = environment * filter_color * (0.92 + 0.12 * fresnel);

	vec3 l1 = normalize(vec3(-3.5, 6.0, 5.0) - p);
	vec3 l2 = normalize(vec3(4.0, 2.0, -3.5) - p);
	vec3 h1 = normalize(l1 + view_direction);
	vec3 h2 = normalize(l2 + view_direction);
	float s1 = pow(max(dot(n, h1), 0.0), 115.0);
	float s2 = pow(max(dot(n, h2), 0.0), 48.0);
	vec3 glint = vec3(1.0, 0.98, 0.83);
	if (u_object == 2) {
		glint = vec3(0.99, 0.99, 1.00);
	}
	color += glint * (0.30 * s1 + 0.11 * s2);
	color += (u_object == 2 ? vec3(0.010) : vec3(0.020, 0.015, 0.004)) * max(dot(n, l1), 0.0);

	if (u_mirror != 0) {
		color *= u_object == 2 ? vec3(0.50, 0.52, 0.57) : vec3(0.57, 0.54, 0.46);
	}

	color = color / (vec3(1.0) + 0.35 * color);
	color = pow(max(color, vec3(0.0)), vec3(0.87));
	frag_color = vec4(color, 1.0);
}
"""


def torus_mesh(major: float, tube: float, rings: int, sides: int):
	"""Interleaved position, normal, UV phase/angle (8 floats per vertex)."""
	if rings < 3 or sides < 3:
		raise ValueError("Torus requires at least three rings and three sides")
	vertices = array("f")
	indices = array("I")
	for i in range(rings + 1):
		u = 2.0 * math.pi * i / rings
		cu, su = math.cos(u), math.sin(u)
		for j in range(sides + 1):
			v = 2.0 * math.pi * j / sides
			cv, sv = math.cos(v), math.sin(v)
			radius = major + tube * cv
			vertices.extend((radius * cu, tube * sv, radius * su,
			                 cv * cu, sv, cv * su, i / rings, v))
	for i in range(rings):
		for j in range(sides):
			a = i * (sides + 1) + j
			b = a + sides + 1
			c = a + 1
			d = b + 1
			indices.extend((a, c, b, b, c, d))
	return vertices, indices


def floor_mesh():
	spread = 70.0
	vertices = array("f")
	for x, z in ((-spread, -spread), (spread, -spread),
	             (spread, spread), (-spread, spread)):
		vertices.extend((x, FLOOR_Y, z, 0.0, 1.0, 0.0, 0.0, 0.0))
	return vertices, array("I", (0, 2, 1, 0, 3, 2))


class GoldenTorusRenderer:
	"""Draw into Qt's currently active OpenGL framebuffer."""

	def __init__(self, ctx):
		self.ctx = ctx
		self.program = ctx.program(vertex_shader=VERTEX_SHADER,
		                           fragment_shader=FRAGMENT_SHADER)
		self._buffers = []
		self._vaos = []
		self.inner = self._make_mesh(*torus_mesh(INNER_MAJOR_RADIUS, INNER_TUBE_RADIUS, 144, 64))
		self.outer = self._make_mesh(*torus_mesh(OUTER_MAJOR_RADIUS, OUTER_TUBE_RADIUS, 2304, 32))
		self.floor = self._make_mesh(*floor_mesh())
		# ModernGL's native texture API is 2D. A one-row R32F texture
		# stores a truly ONE-DIMENSIONAL 2304-sample signal, addressed by phase.
		self.spectrum_texture = ctx.texture(
			(PROFILE_SAMPLES, 1), components=1,
			data=np.zeros(PROFILE_SAMPLES, dtype="f4").tobytes(), dtype="f4"
		)
		self.spectrum_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
		self.spectrum_texture.repeat_x = True
		self.spectrum_texture.repeat_y = False
		self.program["u_spectrum"].value = 0
		self.program["u_inner_scale"].value = INNER_SCALE
		self.program["u_outer_major"].value = OUTER_MAJOR_RADIUS
		self.program["u_outer_tube"].value = OUTER_TUBE_RADIUS
		self.program["u_displace"].value = OUTER_DISPLACE
		self.program["u_rainbow_speed"].value = RAINBOW_SPEED

	def _make_mesh(self, vertices, indices):
		vbo = self.ctx.buffer(vertices.tobytes())
		ibo = self.ctx.buffer(indices.tobytes())
		vao = self.ctx.vertex_array(
			self.program,
			[(vbo, "3f 3f 2f", "in_position", "in_normal", "in_params")],
			index_buffer=ibo,
		)
		self._buffers.extend((vbo, ibo))
		self._vaos.append(vao)
		return vao

	def draw(self, target, size, elapsed: float, bass_pulse: float, spectrum):
		width, height = max(1, size[0]), max(1, size[1])
		spectrum = np.asarray(spectrum, dtype=np.float32)
		if spectrum.shape != (SPECTRUM_BANDS,):
			raise ValueError(f"Expected {SPECTRUM_BANDS} spectrum bands")
		profile = ring_profile(spectrum)
		self.spectrum_texture.write(profile.tobytes())
		self.spectrum_texture.use(location=0)

		target.use()
		self.ctx.viewport = (0, 0, width, height)
		target.clear(0.012, 0.014, 0.029, 1.0, depth=1.0)
		self.ctx.enable(moderngl.DEPTH_TEST)
		self.ctx.disable(moderngl.CULL_FACE)
		self.ctx.disable(moderngl.BLEND)
		self.program["u_time"].value = elapsed
		self.program["u_aspect"].value = width / height
		self.program["u_pulse"].value = BASS_PULSE * max(0.0, min(1.0, bass_pulse))

		# Mirror first, then the translucent floor, then the real objects.
		self.program["u_mirror"].value = 1
		self.program["u_object"].value = 0
		self.inner.render()
		self.program["u_object"].value = 2
		self.outer.render()

		self.ctx.enable(moderngl.BLEND)
		self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
		self.program["u_mirror"].value = 0
		self.program["u_object"].value = 1
		self.floor.render()
		self.ctx.disable(moderngl.BLEND)

		self.program["u_object"].value = 0
		self.inner.render()
		self.program["u_object"].value = 2
		self.outer.render()
		self.ctx.disable(moderngl.DEPTH_TEST)

	def release(self):
		for vao in self._vaos:
			vao.release()
		for buffer in self._buffers:
			buffer.release()
		self.spectrum_texture.release()
		self.program.release()
		self._vaos.clear()
		self._buffers.clear()
