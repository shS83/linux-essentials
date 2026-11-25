"""OpenGL 3.3 attractors: particle textures, additive density and GPU tone mapping.

No particle uploads, histogram arrays, readbacks or GPU waits in draw(). The same
GLSL files are used by the native C++ renderer. Readback is reserved for explicit
screenshots and regression/benchmark tools.
"""
import math
from pathlib import Path

import moderngl

SHADERS = Path(__file__).resolve().parents[1] / 'shaders' / 'attractor'


class AttractorPackRenderer:
    def __init__(self, ctx, count=250_000):
        self.ctx, self.count = ctx, max(1, count)
        self.fixed, self.sized = [], []
        self.programs, self.vaos = {}, {}
        self.size = (0, 0)
        self.front = self.density_front = self.peak_front = self.serial = 0
        self.generation = self.clear_generation = None
        self.burst_generation = 0
        try:
            for name in ('update', 'points', 'fade', 'reduce', 'peak', 'color', 'composite'):
                vertex = 'points.vert' if name == 'points' else 'fullscreen.vert'
                program = ctx.program(vertex_shader=(SHADERS / vertex).read_text(),
                                      fragment_shader=(SHADERS / f'{name}.frag').read_text())
                self.fixed.append(program)
                vao = ctx.vertex_array(program, [])
                self.fixed.append(vao)
                self.programs[name], self.vaos[name] = program, vao
            side = math.ceil(math.sqrt(self.count))
            self.particle_size = (side, math.ceil(self.count / side))
            self.particles = [self._target(self.particle_size, 4, 'f4', self.fixed) for _ in range(2)]
            self.peaks = [self._target((1, 1), 1, 'f4', self.fixed) for _ in range(2)]
            for _, target in self.peaks:
                target.clear(.001)
        except Exception:
            self.release()
            raise

    def _target(self, size, components, dtype, resources):
        texture = self.ctx.texture(size, components, dtype=dtype)
        resources.append(texture)
        texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        texture.repeat_x = texture.repeat_y = False
        target = self.ctx.framebuffer(color_attachments=[texture])
        resources.append(target)
        return texture, target

    def _resize(self, width, height):
        scale = min(1., 1100/max(1, width), 800/max(1, height))
        size = max(1, round(width*scale)), max(1, round(height*scale))
        if size == self.size:
            return
        for resource in reversed(self.sized):
            resource.release()
        self.sized.clear()
        self.size = size
        self.densities = [self._target(size, 1, 'f4', self.sized) for _ in range(2)]
        for _, target in self.densities:
            target.clear()
        self.reductions = []
        w, h = size
        while w > 1 or h > 1:
            w, h = (w+1)//2, (h+1)//2
            self.reductions.append(self._target((w, h), 1, 'f4', self.sized))
        self.colors = self._target(size, 4, 'f1', self.sized)
        self.colors[0].filter = (moderngl.LINEAR, moderngl.LINEAR)
        for _, target in self.peaks:
            target.clear(.001)

    def _pass(self, name, target, uniforms, textures=(), viewport=None):
        target.use()
        self.ctx.viewport = (0, 0, *(viewport or target.size))
        program = self.programs[name]
        for unit, (sampler, texture) in enumerate(textures):
            texture.use(location=unit)
            program[sampler].value = unit
        for key, value in uniforms.items():
            program[key].value = value
        self.vaos[name].render(mode=moderngl.TRIANGLES, vertices=3)

    def draw(self, target, size, scene, elapsed, energy=0., mid=0., treble=0.):
        steps = scene.prepare_frame(elapsed, energy, mid, treble)
        self.ctx.scissor = None
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        self._resize(*size)
        initialize = self.generation != scene.generation
        burst = self.burst_generation != scene.burst_generation
        if self.clear_generation != scene.clear_generation:
            for _, fbo in self.densities:
                fbo.clear()
        if initialize or self.clear_generation != scene.clear_generation:
            for _, fbo in self.peaks:
                fbo.clear(.001)
        parameters = tuple(scene.parameters) + (0.,) * (6-len(scene.parameters))
        bass, dt = scene.frame_bass, scene.frame_dt
        for tick in range(max(steps, int(initialize or burst))):
            back = 1-self.front
            self.serial = (self.serial+1) & 0x7fffffff
            self._pass('update', self.particles[back][1], {
                'kind': scene.current, 'parameters': parameters[:4], 'extra': parameters[4:],
                'drive': 1+1.5*bass, 'rebirth': .005+.02*float(scene.levels[2]),
                'initialize_points': int(initialize and tick == 0),
                'burst': int(burst and tick == 0), 'integrate': int(tick < steps),
                'count': self.count, 'serial': self.serial,
            }, (('particles', self.particles[self.front][0]),))
            self.front = back
            back = 1-self.density_front
            self._pass('fade', self.densities[back][1],
                       {'decay': (.86 if tick < steps else 1.) * (.35 if initialize and tick == 0 else 1.)},
                       (('source', self.densities[self.density_front][0]),))
            self.ctx.enable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
            self.ctx.blend_equation = moderngl.FUNC_ADD
            p = self.programs['points']
            self.particles[self.front][0].use(location=0)
            for key, value in {
                'particles': 0, 'kind': scene.current, 'resolution': tuple(float(v) for v in self.size),
                'angle': float(scene.spin+(scene.pointer[0]*3 if scene.current >= 2 else 0)),
                'tilt': .4+scene.pointer[1]*.8,
                'zoom': min(self.size)/(5.4, 4.4, 62., 3.8)[scene.current]*(1+.10*bass),
            }.items():
                p[key].value = value
            self.vaos['points'].render(mode=moderngl.POINTS, vertices=self.count)
            self.ctx.disable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            self.density_front = back
        source = self.densities[self.density_front][0]
        for texture, fbo in self.reductions:
            self._pass('reduce', fbo, {}, (('source', source),))
            source = texture
        back = 1-self.peak_front
        gain = .9*(1+.9*bass)
        self._pass('peak', self.peaks[back][1], {'gain': gain, 'decay': math.exp(-dt*1.2)},
                   (('maximum', source), ('previous_peak', self.peaks[self.peak_front][0])))
        self.peak_front = back
        self._pass('color', self.colors[1], {'gain': gain, 'phase': float(scene.phase), 'palette': scene.palette},
                   (('density', self.densities[self.density_front][0]), ('peak', self.peaks[back][0])))
        self.colors[0].build_mipmaps()
        self._pass('composite', target, {}, (('color_image', self.colors[0]),), viewport=size)
        self.generation, self.clear_generation = scene.generation, scene.clear_generation
        self.burst_generation = scene.burst_generation

    def release(self):
        for resource in reversed(self.sized + self.fixed):
            resource.release()
        self.sized.clear()
        self.fixed.clear()
