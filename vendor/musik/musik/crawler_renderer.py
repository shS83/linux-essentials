"""Crawler: GPU rainbow particle trails with an audio-reactive plasma composite.

OpenGL 3.3 / ModernGL. Owns only its offscreen resources and does not
capture audio. Input comes from MusiK's existing AudioAnalysis signals.
"""
from __future__ import annotations

from array import array
import colorsys
import math

import moderngl


FULLSCREEN_VERTEX = """
#version 330
out vec2 uv;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

FADE_FRAGMENT = """
#version 330
uniform sampler2D previous_frame;
uniform float decay;
in vec2 uv;
out vec4 frag;
void main() {
    frag = vec4(texture(previous_frame, uv).rgb * decay, 1.0);
}
"""

PARTICLE_VERTEX = """
#version 330
in vec2 in_position;
in vec2 in_local;
in vec3 in_color;
out vec2 local_uv;
out vec3 color;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    local_uv = in_local;
    color = in_color;
}
"""

PARTICLE_FRAGMENT = """
#version 330
in vec2 local_uv;
in vec3 color;
out vec4 frag;
void main() {
    float r = length(local_uv);
    if (r >= 1.0) discard;
    float halo = exp(-r*r*13.0) * 0.25;
    float inner = (1.0 - smoothstep(0.09, 0.30, r)) * 0.72;
    float hot = (1.0 - smoothstep(0.015, 0.095, r)) * 0.75;
    vec3 rgb = color * (halo + inner) + vec3(hot);
    frag = vec4(rgb, 1.0);
}
"""

COMPOSITE_FRAGMENT = """
#version 330
uniform sampler2D trail;
uniform vec2 render_resolution;
uniform vec2 trail_resolution;
uniform float elapsed;
uniform float energy;
uniform float mid;
uniform float treble;
uniform float bass;
uniform int plasma_on;
uniform int bloom_on;
uniform int scanlines_on;
uniform int vignette_on;
in vec2 uv;
out vec4 frag;

vec3 hsv(float h, float s, float v) {
    vec3 rgb = clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return v * mix(vec3(1.0), rgb, s);
}

void main() {
    float t = elapsed;
    vec2 p = (uv - 0.5) * vec2(render_resolution.x / max(render_resolution.y, 1.0), 1.0);
    vec3 background = vec3(0.006, 0.003, 0.014);
    if (plasma_on != 0) {
        float v = sin(p.x*5.1 + t*0.26) + sin(p.y*6.8 - t*0.29);
        v += sin((p.x + p.y)*4.2 + t*0.21);
        v += sin(length(p + 0.25*vec2(sin(t*0.13),cos(t*0.17)))*12.0 - t*0.32);
        float wave = clamp(0.5 + v*0.125, 0.0, 1.0);
        float hue = fract(t*0.012 + wave*0.30 + mid*0.12);
        float strength = (0.012 + 0.035*wave) * (0.7 + energy*0.7);
        background += hsv(hue, 0.72, strength);
    }

    vec3 rays = texture(trail, uv).rgb;
    if (bloom_on != 0) {
        vec2 d = 2.5 / trail_resolution;
        vec3 blur = vec3(0.0);
        blur += texture(trail, uv + vec2( d.x, 0.0)).rgb;
        blur += texture(trail, uv + vec2(-d.x, 0.0)).rgb;
        blur += texture(trail, uv + vec2(0.0,  d.y)).rgb;
        blur += texture(trail, uv + vec2(0.0, -d.y)).rgb;
        blur += texture(trail, uv + d).rgb;
        blur += texture(trail, uv - d).rgb;
        blur += texture(trail, uv + vec2(d.x, -d.y)).rgb;
        blur += texture(trail, uv + vec2(-d.x, d.y)).rgb;
        rays += blur * (0.040 + 0.020 * bass);
    }
    vec3 color = background + rays * (0.90 + 0.08*treble);
    if (vignette_on != 0) {
        float dist = length(p * vec2(0.90, 1.0));
        color *= 1.0 - 0.32*smoothstep(0.30, 1.2, dist);
    }
    if (scanlines_on != 0) {
        float line = 0.965 + 0.035*sin(uv.y * render_resolution.y * 3.14159265);
        color *= line;
    }
    // Reinhard-like soft clip retains saturated neon highlights.
    color = color / (1.0 + max(color - vec3(0.8), vec3(0.0))*0.30);
    frag = vec4(color, 1.0);
}
"""


def _clamp(value, low=0.0, high=1.0):
	return max(low, min(high, float(value)))


class CrawlerRenderer:
	"""Two low-res feedback FBOs + sprite batches + one full-res composite."""

	def __init__(self, ctx, render_scale=0.5):
		self.ctx = ctx
		self.render_scale = render_scale
		self.fade_program = ctx.program(vertex_shader=FULLSCREEN_VERTEX, fragment_shader=FADE_FRAGMENT)
		self.composite_program = ctx.program(vertex_shader=FULLSCREEN_VERTEX, fragment_shader=COMPOSITE_FRAGMENT)
		self.particle_program = ctx.program(vertex_shader=PARTICLE_VERTEX, fragment_shader=PARTICLE_FRAGMENT)
		self.fade_vao = ctx.vertex_array(self.fade_program, [])
		self.composite_vao = ctx.vertex_array(self.composite_program, [])
		self.vbo = ctx.buffer(reserve=512 * 6 * 7 * 4, dynamic=True)
		self.particle_vao = ctx.vertex_array(
			self.particle_program,
			[(self.vbo, '2f 2f 3f', 'in_position', 'in_local', 'in_color')],
		)
		self.composite_program['trail'].value = 0
		self.fade_program['previous_frame'].value = 0
		self.targets = []
		self.textures = []
		self.size = (0, 0)
		self.front = 0

	def _resize_if_needed(self, width, height):
		size = (max(1, int(width * self.render_scale)),
		        max(1, int(height * self.render_scale)))
		if size == self.size:
			return
		for fbo in self.targets:
			fbo.release()
		for texture in self.textures:
			texture.release()
		self.targets = []
		self.textures = []
		for _ in range(2):
			texture = self.ctx.texture(size, components=4)
			texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
			texture.repeat_x = texture.repeat_y = False
			fbo = self.ctx.framebuffer(color_attachments=[texture])
			fbo.clear(0.0, 0.0, 0.0, 1.0)
			self.textures.append(texture)
			self.targets.append(fbo)
		self.size = size
		self.front = 0

	def clear_trails(self):
		for fbo in self.targets:
			fbo.clear(0.0, 0.0, 0.0, 1.0)

	@staticmethod
	def _quad(vertices, x, y, radius, color, width, height):
		if x + radius < 0 or x - radius > width or y + radius < 0 or y - radius > height:
			return
		left = (x-radius)*2/width-1
		right = (x+radius)*2/width-1
		bottom = 1-(y+radius)*2/height
		top = 1-(y-radius)*2/height
		r, g, b = color
		# Two triangles, attributes: position.xy, local.xy, color.rgb
		for px, py, ux, uy in ((left,bottom,-1,-1), (right,bottom,1,-1),
		                       (left,top,-1,1), (left,top,-1,1),
		                       (right,bottom,1,-1), (right,top,1,1)):
			vertices.extend((px,py,ux,uy,r,g,b))

	def _vertices(self, width, height, t, count, energy, mid, treble, bass):
		vertices = array('f')
		zoom = 0.99 + 0.07*math.sin(t*0.20) + bass * 0.16
		xs = zoom * (1.0 + 0.032*math.sin(t*0.16))
		ys = zoom * (1.0 + 0.037*math.cos(t*0.19))
		cx = width * (0.5 + 0.009 * math.sin(t*0.21))
		cy = height * (0.5 + 0.009 * math.cos(t*0.18))
		geo_scale = min(width / 640.0, height / 480.0)
		phase = t * (1.34 + 0.13*mid) + 0.75*math.sin(t*0.27)
		base_radius = geo_scale * (2.3 + 1.2*math.sin(t*0.40) + 1.9*energy)
		step = 180.0/count
		for i in range(1, count):
			angle = step*i + phase
			dist = math.pi * i
			x = cx + (math.sin(angle)*dist + step)*geo_scale*xs
			y = cy + (math.cos(angle)*dist + step)*geo_scale*ys
			hue = (t*.047 + i/count*.86 + mid*.12) % 1.0
			color = colorsys.hsv_to_rgb(hue, 0.86, 0.58 + 0.25*bass)
			radius = max(1.0, base_radius * (1.0 + .18*math.sin(t*.75+i*.17)))
			self._quad(vertices, x, y, radius * 3.7, color, width, height)
		# Bright but bounded transient glints on high notes; deterministic (no random jitter).
		if treble > 0.12:
			for j in range(min(25, int(treble*26)+3)):
				i = 1 + (j * 31) % max(1, count - 1)
				angle = step*i + phase
				dist = math.pi*i
				x = cx + (math.sin(angle)*dist+step)*geo_scale*xs
				y = cy + (math.cos(angle)*dist+step)*geo_scale*ys
				x += math.sin(t*9+j*7)*geo_scale*5
				y += math.cos(t*11+j*3)*geo_scale*5
				self._quad(vertices, x, y, geo_scale*(3+3*treble), (0.65, 0.85, 1.0), width, height)
		return vertices

	def draw(self, target, viewport, t, dt, count, trail_alpha, energy,
	         mid, treble, bass, *, paused=False, clear=False, plasma=True,
	         bloom=True, scanlines=True, vignette=True):
		width, height = viewport
		self._resize_if_needed(width, height)
		if clear:
			self.clear_trails()
		if not paused:
			back = 1-self.front
			self.targets[back].use()
			self.ctx.viewport = (0, 0, *self.size)
			self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
			self.textures[self.front].use(location=0)
			# Time-correct 60 FPS trail fade; 14/255 approximately matches Pygame alpha.
			decay = (1.0-_clamp(trail_alpha/255.0))**(min(0.10, max(0.0,dt))*60)
			self.fade_program['decay'].value = decay
			self.fade_vao.render(mode=moderngl.TRIANGLES, vertices=3)
			vertices = self._vertices(*self.size, t, count, energy, mid, treble, bass)
			if vertices:
				payload = vertices.tobytes()
				self.vbo.write(payload)
				self.ctx.enable(moderngl.BLEND)
				self.ctx.blend_func = (moderngl.ONE, moderngl.ONE)
				self.particle_vao.render(mode=moderngl.TRIANGLES, vertices=len(vertices)//7)
				self.ctx.disable(moderngl.BLEND)
			self.front = back

		# Always use Qt's current default FBO, which is not guaranteed to be #0.
		target.use()
		self.ctx.viewport = (0, 0, width, height)
		self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
		self.textures[self.front].use(location=0)
		p = self.composite_program
		p['render_resolution'].value = (float(width), float(height))
		p['trail_resolution'].value = tuple(float(n) for n in self.size)
		p['elapsed'].value = t
		p['energy'].value = _clamp(energy)
		p['mid'].value = _clamp(mid)
		p['treble'].value = _clamp(treble)
		p['bass'].value = _clamp(bass)
		for key, enabled in (('plasma_on', plasma), ('bloom_on', bloom),
		                     ('scanlines_on', scanlines), ('vignette_on', vignette)):
			p[key].value = int(enabled)
		self.composite_vao.render(mode=moderngl.TRIANGLES, vertices=3)

	def release(self):
		for resource in (self.particle_vao, self.fade_vao, self.composite_vao,
		                 self.vbo, self.particle_program, self.fade_program,
		                 self.composite_program, *self.targets, *self.textures):
			resource.release()
		self.targets = []
		self.textures = []
