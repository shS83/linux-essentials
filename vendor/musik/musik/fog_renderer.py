"""Original Fog 3D shS + live contour oscilloscope, rendered in a Qt GL FBO.

Runtime dependencies intentionally match MusiK's existing Python stack.
The original font mesh was baked with tools/generate_fog_mesh.py so there is
no matplotlib/Shapely dependency or heavy text processing at startup.
"""
from __future__ import annotations

import math
from pathlib import Path

import moderngl
import numpy as np

from . import fog_shaders as shaders


FOG_DENSITY = 1.05
BLOOM_STRENGTH = 1.55
BLUR_PASSES = 5
AUDIO_SAMPLES = 512


def normalize(v):
    v = np.asarray(v, dtype=np.float32)
    length = np.linalg.norm(v)
    return v if length < 1e-8 else v / length


def perspective(fovy_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2)
    mat = np.zeros((4, 4), dtype=np.float32)
    mat[0, 0] = f / aspect
    mat[1, 1] = f
    mat[2, 2] = (far + near) / (near - far)
    mat[2, 3] = 2 * far * near / (near - far)
    mat[3, 2] = -1
    return mat


def look_at(eye, target, up):
    eye, target, up = [np.asarray(a, dtype=np.float32) for a in (eye, target, up)]
    forward = normalize(target - eye)
    side = normalize(np.cross(forward, up))
    upward = np.cross(side, forward)
    mat = np.eye(4, dtype=np.float32)
    mat[0, :3] = side
    mat[1, :3] = upward
    mat[2, :3] = -forward
    mat[0, 3] = -np.dot(side, eye)
    mat[1, 3] = -np.dot(upward, eye)
    mat[2, 3] = np.dot(forward, eye)
    return mat


def model_matrix(t):
    ay, ax = t * .55, t * .28
    cy, sy = math.cos(ay), math.sin(ay)
    cx, sx = math.cos(ax), math.sin(ax)
    yrot = np.array([[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1]], dtype=np.float32)
    xrot = np.array([[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1]], dtype=np.float32)
    move = np.eye(4, dtype=np.float32)
    move[1, 3] = math.sin(t * .8) * .035
    return move @ yrot @ xrot


def resample_waveform(samples, count=AUDIO_SAMPLES):
    """Bound input memory; use the newest samples, never an unbounded queue."""
    a = np.asarray(samples, dtype=np.float32).reshape(-1)
    if len(a) == 0:
        return np.zeros(count, dtype=np.float32)
    # At most 4096 latest samples are useful; transient allocation is bounded.
    a = np.nan_to_num(a[-4096:], nan=0., posinf=0., neginf=0.)
    if len(a) == 1:
        return np.full(count, float(np.clip(a[0], -1, 1)), dtype=np.float32)
    if len(a) == count:
        return np.clip(a, -1, 1).copy()
    return np.interp(np.linspace(0, len(a) - 1, count),
                     np.arange(len(a)), a).clip(-1, 1).astype(np.float32)


class FogRenderer:
    """GL ownership stays on the Qt widget's OpenGL thread/context."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.resources = []
        self.targets = []
        self.render_size = None
        self.window_size = None
        self.fog_program = self._program(shaders.FULLSCREEN_VERTEX, shaders.FOG_FRAGMENT)
        self.text_program = self._program(shaders.TEXT_VERTEX, shaders.TEXT_FRAGMENT)
        self.glow_program = self._program(shaders.TEXT_VERTEX, shaders.GLOW_FRAGMENT)
        self.blur_program = self._program(shaders.FULLSCREEN_VERTEX, shaders.BLUR_FRAGMENT)
        self.composite_program = self._program(shaders.FULLSCREEN_VERTEX, shaders.COMPOSITE_FRAGMENT)
        self.fog_vao = self._quad(self.fog_program)
        self.blur_vao = self._quad(self.blur_program)
        self.composite_vao = self._quad(self.composite_program)

        path = Path(__file__).with_name('fog_mesh.npz')
        with np.load(path, allow_pickle=False) as archive:
            vertices = np.ascontiguousarray(archive['mesh'], dtype=np.float32)
        if vertices.ndim != 2 or vertices.shape[1] != 10:
            raise ValueError('Invalid fog_shS vertex asset')
        self.mesh_count = len(vertices)
        self.vbo = self.ctx.buffer(vertices.tobytes())
        self.resources.append(self.vbo)
        layout = '3f 3f 2f 2f'
        attributes = ('in_pos', 'in_normal', 'in_edge', 'in_phase_weight')
        self.text_vao = self.ctx.vertex_array(self.text_program, [(self.vbo, layout, *attributes)])
        self.glow_vao = self.ctx.vertex_array(self.glow_program, [(self.vbo, layout, *attributes)])
        self.resources.extend((self.text_vao, self.glow_vao))
        self.audio_texture = self.ctx.texture((AUDIO_SAMPLES, 1), 1,
                                              data=np.zeros(AUDIO_SAMPLES, dtype=np.float32).tobytes(),
                                              dtype='f4')
        self.audio_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.audio_texture.repeat_x = True
        self.resources.append(self.audio_texture)
        self.camera_pos = (0., 0., 3.3)
        self.view = look_at(self.camera_pos, (0, 0, 0), (0, 1, 0))
        self.blur_program['u_texture'].value = 0
        self.composite_program['u_scene'].value = 0
        self.composite_program['u_bloom'].value = 1
        self.text_program['u_audio'].value = 2
        self.glow_program['u_audio'].value = 2
        self.updated_audio = np.zeros(AUDIO_SAMPLES, dtype=np.float32)

    def _program(self, vertex, fragment):
        obj = self.ctx.program(vertex_shader=vertex, fragment_shader=fragment)
        self.resources.append(obj)
        return obj

    def _quad(self, program):
        vao = self.ctx.vertex_array(program, [])
        self.resources.append(vao)
        return vao

    def _release_targets(self):
        for resource in reversed(self.targets):
            resource.release()
        self.targets.clear()
        self.render_size = None
        self.window_size = None

    def _ensure_targets(self, size):
        if size == self.window_size:
            return
        self._release_targets()
        self.window_size = size
        # Limit intermediate HDR buffer memory on 4K and high-DPI displays.
        w, h = size
        scale = min(1., 1920 / max(1, w), 1080 / max(1, h))
        self.render_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        w, h = self.render_size
        def texture():
            obj = self.ctx.texture((w, h), 4, dtype='f2')
            obj.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.targets.append(obj)
            return obj
        self.scene_tex = texture()
        depth = self.ctx.depth_renderbuffer((w, h))
        self.targets.append(depth)
        self.scene_fbo = self.ctx.framebuffer(color_attachments=[self.scene_tex], depth_attachment=depth)
        self.targets.append(self.scene_fbo)
        self.glow_tex = texture()
        self.glow_fbo = self.ctx.framebuffer(color_attachments=[self.glow_tex])
        self.targets.append(self.glow_fbo)
        self.blur_tex_a = texture()
        self.blur_fbo_a = self.ctx.framebuffer(color_attachments=[self.blur_tex_a])
        self.targets.append(self.blur_fbo_a)
        self.blur_tex_b = texture()
        self.blur_fbo_b = self.ctx.framebuffer(color_attachments=[self.blur_tex_b])
        self.targets.append(self.blur_fbo_b)

    def draw(self, qt_framebuffer, size, t, waveform, energy, pulse, mid, treble, dt):
        self._ensure_targets(size)
        w, h = self.render_size
        ctx = self.ctx
        ctx.viewport = (0, 0, w, h)
        ctx.disable(moderngl.BLEND | moderngl.DEPTH_TEST)
        # Audio sample upload once per video frame, never per QAudioBuffer event.
        alpha = 1.0 - math.exp(-max(0., dt) * 18.)
        self.updated_audio += (waveform - self.updated_audio) * alpha
        self.audio_texture.write(self.updated_audio.tobytes())
        self.audio_texture.use(location=2)
        model = model_matrix(t)
        proj = perspective(48., w / h, .1, 100.)
        matrices = {'u_model': model.T.tobytes(), 'u_view': self.view.T.tobytes(),
                    'u_proj': proj.T.tobytes()}
        wave_strength = .075 + .060 * mid + .055 * treble + .12 * pulse
        light = (math.cos(t * .7) * 1.6, 1., 2.2)
        for program in (self.text_program, self.glow_program):
            for key, value in matrices.items():
                program[key].write(value)
            program['u_time'].value = t
            program['u_wave_strength'].value = wave_strength
            program['u_beat'].value = pulse
            program['u_camera_pos'].value = self.camera_pos
        self.text_program['u_light_pos'].value = light

        self.scene_fbo.use()
        self.scene_fbo.clear(0, 0, 0, 1, depth=1.)
        self.fog_program['u_time'].value = t
        self.fog_program['u_density'].value = FOG_DENSITY + .18 * energy
        self.fog_program['u_resolution'].value = (w, h)
        self.fog_vao.render(moderngl.TRIANGLES, vertices=3)
        ctx.enable(moderngl.DEPTH_TEST)
        self.text_vao.render(moderngl.TRIANGLES)
        ctx.disable(moderngl.DEPTH_TEST)

        self.glow_fbo.use()
        self.glow_fbo.clear(0, 0, 0, 1)
        self.glow_vao.render(moderngl.TRIANGLES)
        source = self.glow_tex
        for _ in range(BLUR_PASSES):
            source.use(location=0)
            self.blur_fbo_a.use()
            self.blur_fbo_a.clear(0, 0, 0, 1)
            self.blur_program['u_direction'].value = (1./w, 0.)
            self.blur_vao.render(moderngl.TRIANGLES, vertices=3)
            self.blur_tex_a.use(location=0)
            self.blur_fbo_b.use()
            self.blur_fbo_b.clear(0, 0, 0, 1)
            self.blur_program['u_direction'].value = (0., 1./h)
            self.blur_vao.render(moderngl.TRIANGLES, vertices=3)
            source = self.blur_tex_b

        qt_framebuffer.use()
        ctx.viewport = (0, 0, *size)
        self.scene_tex.use(location=0)
        self.blur_tex_b.use(location=1)
        self.composite_program['u_bloom_strength'].value = BLOOM_STRENGTH + .20 * pulse
        self.composite_vao.render(moderngl.TRIANGLES, vertices=3)

    def release(self):
        self._release_targets()
        for resource in reversed(self.resources):
            resource.release()
        self.resources.clear()
