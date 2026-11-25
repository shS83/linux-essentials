#version 330 core
in vec2 uv;
out vec4 color;
uniform vec2 resolution;
uniform float angle;

mat3 rotateX(float a) {
    float c = cos(a), s = sin(a);
    return mat3(1,0,0, 0,c,s, 0,-s,c);
}
mat3 rotateY(float a) {
    float c = cos(a), s = sin(a);
    return mat3(c,0,-s, 0,1,0, s,0,c);
}
vec3 scene(vec2 pixel) {
    vec2 p = (pixel - 0.5) * vec2(resolution.x / resolution.y, 1.0);
    p.y -= 0.055;
    vec3 background = mix(vec3(0.022, 0.033, 0.040), vec3(0.065, 0.080, 0.086),
                          exp(-3.2 * dot(p, p)));
    // Analytic ray/box intersection: a real perspective cube, with flat white faces.
    mat3 model = rotateY(angle + 0.58) * rotateX(0.44 + 0.12 * sin(angle * 0.7));
    vec3 ro = transpose(model) * vec3(0, 0, 4.8);
    vec3 rd = transpose(model) * normalize(vec3(p * 3.6, -4.0));
    vec3 inv = 1.0 / rd;
    vec3 t0 = (-vec3(0.67) - ro) * inv;
    vec3 t1 = ( vec3(0.67) - ro) * inv;
    vec3 nearPlane = min(t0, t1), farPlane = max(t0, t1);
    float enter = max(max(nearPlane.x, nearPlane.y), nearPlane.z);
    float leave = min(min(farPlane.x, farPlane.y), farPlane.z);
    if (enter > max(leave, 0.0)) return background;
    vec3 hit = ro + rd * enter;
    vec3 normal = normalize(step(vec3(0.6699), abs(hit)) * sign(hit));
    normal = model * normal;
    float diffuse = max(dot(normal, normalize(vec3(-0.5, 0.9, 1.4))), 0.0);
    float shade = 0.48 + 0.51 * diffuse;
    return vec3(shade);
}
void main() {
    // Four subpixel samples keep the source silhouette clean under refraction.
    vec3 c = vec3(0);
    for (int x = 0; x < 2; ++x)
        for (int y = 0; y < 2; ++y)
            c += scene(uv + (vec2(x,y) - 0.5) * 0.5 / resolution);
    color = vec4(c * 0.25, 1);
}
