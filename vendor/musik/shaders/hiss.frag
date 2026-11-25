#version 330 core
in vec2 uv;
out vec4 color;
uniform sampler2D source;
uniform vec2 resolution;
uniform float time;
uniform float strength;
uniform float dispersion;
uniform float turbulence;

// A procedural curl-like field. Domain warping bends its eddies into
// elongated, evolving filaments; this is not an incompressible fluid solver.
vec2 velocity(vec2 p) {
    float t = time;
    vec2 q = p * (6.0 + turbulence * 9.0);
    q += 0.8 * vec2(sin(q.y * 0.71 + t * 0.9), cos(q.x * 0.63 - t * 0.7));
    vec2 v = vec2(cos(q.y + t) * sin(q.x - t * 0.4),
                 -cos(q.x - t * 0.4) * sin(q.y + t));
    v += 0.42 * vec2(cos(q.y * 1.9 - t * 1.2) * sin(q.x * 1.7 + t * 0.6),
                    -cos(q.x * 1.7 + t * 0.6) * sin(q.y * 1.9 - t * 1.2));
    v += 0.17 * vec2(sin(q.y * 3.7 + q.x + t), cos(q.x * 3.1 - q.y - t));
    return v;
}

void main() {
    if (strength == 0.0 && dispersion == 0.0) {
        color = texture(source, uv);
        return;
    }
    vec2 aspect = vec2(resolution.x / resolution.y, 1.0);
    vec2 origin = (uv - vec2(0.5, 0.555)) * aspect;
    // Keep the effect around the subject, with a smooth boundary into the scene.
    float envelope = 1.0 - smoothstep(0.19, 0.49, length(origin * vec2(1.0, 0.88)));
    vec2 p = origin;
    float stepSize = strength * 0.050 * envelope;
    // Backtrace the sample coordinates through the velocity field (midpoint RK2).
    for (int i = 0; i < 7; ++i) {
        vec2 v = velocity(p);
        p -= stepSize * velocity(p - 0.5 * stepSize * v);
    }
    vec2 sampleUV = uv + (p - origin) / aspect;
    vec2 chroma = dispersion * 0.035 * envelope *
                  (velocity(p) + vec2(0.32, 0.12)) / aspect;
    // Each channel sees a slightly different refractive index.
    vec3 c = vec3(texture(source, sampleUV + chroma).r,
                  texture(source, sampleUV).g,
                  texture(source, sampleUV - chroma).b);
    color = vec4(c, 1);
}
