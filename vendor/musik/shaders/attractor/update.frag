#version 330 core
uniform sampler2D particles;
uniform int kind;
uniform vec4 parameters;
uniform vec2 extra;
uniform float drive;
uniform float rebirth;
uniform int initialize_points;
uniform int burst;
uniform int integrate;
uniform int count;
uniform int serial;
layout(location=0) out vec4 position;
uint hash(uint x) {
    x ^= x >> 16; x *= 0x7feb352du;
    x ^= x >> 15; x *= 0x846ca68bu;
    return x ^ (x >> 16);
}
float random(inout uint state) {
    state = hash(state + 0x9e3779b9u);
    return float(state >> 8) * (1.0 / 16777216.0);
}
vec3 seed(inout uint state) {
    vec3 r = vec3(random(state), random(state), random(state));
    if (kind == 2) return mix(vec3(-15,-20,5), vec3(15,20,40), r);
    if (kind == 3) return mix(vec3(-.8,-.8,-.2), vec3(.8,.8,1.2), r);
    return vec3(r.xy * 2.0 - 1.0, 0.0);
}
void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    int index = pixel.y * textureSize(particles,0).x + pixel.x;
    if (index >= count) { position = vec4(0); return; }
    uint state = hash(uint(index) ^ (uint(serial) * 0x9e3779b9u));
    vec3 p = initialize_points != 0 ? seed(state) : texelFetch(particles,pixel,0).xyz;
    if (burst != 0 && index < count / 3) { p = seed(state); p.xy *= 1.8; }
    vec4 q = parameters;
    if (integrate != 0) {
        if (kind == 0) p.xy = vec2(sin(q.x*p.y)+q.z*cos(q.x*p.x), sin(q.y*p.x)+q.w*cos(q.y*p.y));
        else if (kind == 1) p.xy = vec2(sin(q.x*p.y)-cos(q.y*p.x), sin(q.z*p.x)-cos(q.w*p.y));
        else {
            float dt = (kind == 2 ? .006 : .011) * drive;
            for (int i=0; i<2; ++i) {
                vec3 delta;
                if (kind == 2) delta = vec3(q.x*(p.y-p.x), p.x*(q.y-p.z)-p.y, p.x*p.y-q.z*p.z);
                else delta = vec3((p.z-q.y)*p.x-q.w*p.y, q.w*p.x+(p.z-q.y)*p.y,
                    q.z+q.x*p.z-p.z*p.z*p.z/3.0-(p.x*p.x+p.y*p.y)*(1.0+extra.x*p.z)+extra.y*p.z*p.x*p.x*p.x);
                p += delta * dt;
            }
        }
    }
    float limit = kind == 0 ? 10.0 : kind == 1 ? 6.0 : kind == 2 ? 150.0 : 8.0;
    if (any(isnan(p)) || any(isinf(p)) || any(greaterThanEqual(abs(p),vec3(limit)))) p = seed(state);
    if (integrate != 0 && random(state) < rebirth) p = seed(state);
    position = vec4(p,1);
}
