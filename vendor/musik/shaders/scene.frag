// Fog noise and domain warping adapted from ../Fog/fog.py.

#version 330

uniform float u_time;
uniform float u_density;
uniform float u_speed;
uniform vec2 u_resolution;
uniform float u_pulse;
uniform float u_kick;
uniform vec3 u_flash;
uniform float u_mid;
uniform float u_treble;

in vec2 uv;

out vec4 fragColor;


// ------------------------------------------------------------
// Hash
// ------------------------------------------------------------

float hash21(vec2 p)
{
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);

    return fract(p.x * p.y);
}


// ------------------------------------------------------------
// Smooth value noise
// ------------------------------------------------------------

float noise(vec2 p)
{
    vec2 i = floor(p);
    vec2 f = fract(p);

    f = f * f * (3.0 - 2.0 * f);

    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));

    return mix(
        mix(a, b, f.x),
        mix(c, d, f.x),
        f.y
    );
}


// ------------------------------------------------------------
// Fractal Brownian Motion
// ------------------------------------------------------------

float fbm(vec2 p)
{
    float result = 0.0;
    float amplitude = 0.5;

    mat2 rotation = mat2(
         0.80, 0.60,
        -0.60, 0.80
    );

    for (int i = 0; i < 4; ++i)
    {
        result += amplitude * noise(p);

        p = rotation * p;
        p *= 2.03;
        p += vec2(17.1, 9.2);

        amplitude *= 0.5;
    }

    return result;
}


// ------------------------------------------------------------
// Smoke/fog field
//
// Tässä tärkein ero tavalliseen scrollaavaan noiseen:
//
// toinen noise-kenttä vääntää varsinaisen sumukentän
// koordinaatteja.
//
// Tämän ansiosta pilvet virtaavat, kiertyvät ja hajoavat.
// ------------------------------------------------------------

float fog_layer(
    vec2 p,
    float scale,
    vec2 drift,
    float seed
)
{
    float t = u_time * u_speed;

    p *= scale;

    // Hidas koko kerroksen liike
    p += drift * t;

    // Domain warp
    vec2 warp;

    warp.x = fbm(
        p * 0.72 +
        vec2(
            seed + t * 0.018,
            seed * 2.1 - t * 0.012
        )
    );

    warp.y = fbm(
        p * 0.72 +
        vec2(
            seed * 3.7 - t * 0.014,
            seed + 5.2 + t * 0.017
        )
    );

    warp -= 0.5;

    // Melko voimakas vääristys tekee savumaisia kaaria
    p += warp * 2.2;

    // Varsinainen sumupilvi
    float cloud = fbm(
        p +
        vec2(
            t * 0.009,
            -t * 0.015
        )
    );

    // Suuri hidas kenttä hajottaa pilviä suuremmiksi
    // sumulautoiksi.
    float envelope = fbm(
        p * 0.31 +
        vec2(seed * 5.1, t * 0.006)
    );

    // Ei tehdä sumusta liian kiinteää.
    float density = smoothstep(
        0.43,
        0.73,
        cloud
    );

    density *= smoothstep(
        0.18,
        0.72,
        envelope
    );

    return pow(density, 1.15);
}


// ------------------------------------------------------------


vec3 sky(vec3 direction) {
    float h = clamp(direction.y * 0.65 + 0.22, 0.0, 1.0);
    vec3 color = mix(vec3(0.19, 0.075, 0.24), vec3(0.025, 0.018, 0.085), h);
    color += vec3(0.40, 0.18, 0.10) * exp(-abs(direction.y) * 7.0);
    color += u_flash * u_pulse * (0.22 + 0.35 * exp(-abs(direction.y) * 3.0));
    return color;
}

vec3 floorColor(vec3 point, float distanceToEye) {
    vec2 tile = point.xz * 0.60;
    // Analytic filtering keeps the horizon from flickering with tiny squares.
    vec2 width = max(fwidth(tile), vec2(0.001));
    vec2 lo = tile - width * 0.5;
    vec2 hi = tile + width * 0.5;
    vec2 average = (abs(fract(hi * 0.5) - 0.5) - abs(fract(lo * 0.5) - 0.5)) * 2.0 / width;
    float checker = clamp(0.5 + 0.5 * average.x * average.y, 0.0, 1.0);
    vec3 color = mix(vec3(0.025, 0.022, 0.052), vec3(0.63, 0.58, 0.68), checker);
    float shadow = 1.0 - 0.76 * exp(-dot(point.xz, point.xz) * 0.60);
    color *= shadow;
    color += u_flash * u_pulse * 0.12;
    return mix(color, sky(vec3(0.0)), 1.0 - exp(-distanceToEye * 0.032));
}

vec3 environment(vec3 origin, vec3 direction) {
    if (direction.y < -0.001) {
        float t = -origin.y / direction.y;
        return floorColor(origin + direction * t, t);
    }
    vec3 color = sky(direction);
    // Broad studio lights reflected in the chrome surface.
    color += vec3(1.8, 1.65, 1.45) * pow(max(dot(direction, normalize(vec3(-1.3, 1.8, 1.0))), 0.0), 22.0);
    color += vec3(0.5, 0.7, 1.3) * pow(max(dot(direction, normalize(vec3(1.5, 0.7, 0.2))), 0.0), 38.0);
    color += vec3(0.8) * smoothstep(0.985, 0.998, dot(direction, normalize(vec3(0.2, 1.0, -0.8))));
    return color;
}

float spikeHeight() {
    return 1.35 * log(1.0 + 5.0 * clamp(u_treble, 0.0, 1.0)) / log(6.0);
}

float sphereField(vec3 q, float radius) {
    // Broad midrange waves remain underneath outward-pointing treble spikes.
    vec3 midPhase = q * vec3(3.8, 4.6, 3.4) + u_time * vec3(3.1, -2.7, 2.3);
    vec3 midWave = sin(midPhase);
    float distanceFromCenter = length(q);
    vec3 direction = q / max(distanceFromCenter, 0.001);
    float angle = u_time * 0.35;
    mat2 rotation = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
    direction.xz = rotation * direction.xz;
    direction.yz = rotation * direction.yz;
    vec3 a = abs(direction);
    // Nearest of 26 directions: six axes, eight cube corners and twelve edges.
    // Symmetry replaces a loop over individual spikes.
    float alignment = max(max(a.x, a.y), a.z);
    alignment = max(alignment, (a.x + a.y + a.z) * 0.577350269);
    alignment = max(alignment, max(max(a.x + a.y, a.x + a.z), a.y + a.z) * 0.707106781);
    float tipDistance = sqrt(max(0.0, 2.0 - 2.0 * alignment));
    // Rounded shoulders meet the sphere with zero slope; a curved taper
    // pulls the same surface into a tip instead of attaching a straight cone.
    float width = 0.34 + 0.06 * u_treble;
    float shoulder = 1.0 - smoothstep(0.0, width, tipDistance);
    float spike = pow(shoulder, 2.5);
    float displacement = 0.11 * u_mid * midWave.x * midWave.y * midWave.z
                       + spikeHeight() * spike;
    return distanceFromCenter - radius - displacement;
}

vec3 sphereNormal(vec3 q, float radius) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        sphereField(q + e.xyy, radius) - sphereField(q - e.xyy, radius),
        sphereField(q + e.yxy, radius) - sphereField(q - e.yxy, radius),
        sphereField(q + e.yyx, radius) - sphereField(q - e.yyx, radius)
    ));
}

void main() {
    vec2 p = (gl_FragCoord.xy - u_resolution * 0.5) / u_resolution.y;
    // Orbit around the fixed center of the chrome sphere.
    // A full revolution takes about 52 seconds at 0.12 rad/s.
    float orbitAngle = u_time * 0.12;
    float orbitRadius = 7.0;
    vec3 target = vec3(0.0, 1.38, 0.0);
    vec3 eye = vec3(sin(orbitAngle) * orbitRadius,
                    2.0,
                    cos(orbitAngle) * orbitRadius);
    vec3 forward = normalize(target - eye);
    vec3 worldUp = vec3(0.0, 1.0, 0.0);
    vec3 right = normalize(cross(forward, worldUp));
    vec3 up = normalize(cross(right, forward));
    vec3 ray = normalize(forward * 1.45 + right * p.x * 2.0 + up * p.y * 2.0);
    vec3 color = sky(ray);
    float distanceToEye = 1000.0;
    if (ray.y < -0.001) {
        distanceToEye = -eye.y / ray.y;
        color = floorColor(eye + ray * distanceToEye, distanceToEye);
    }

    float kick = clamp(u_kick, 0.0, 1.0);
    float radius = 1.0 + kick * 0.045;
    vec3 center = target + normalize(eye - target) * kick * 0.12;
    vec3 oc = eye - center;
    float b = dot(oc, ray);
    float bound = radius + 0.11 * u_mid + spikeHeight();
    float discriminant = b * b - dot(oc, oc) + bound * bound;
    bool sphere = false;
    if (discriminant > 0.0) {
        float hit = max(0.0, -b - sqrt(discriminant));
        float exitDistance = min(-b + sqrt(discriminant), distanceToEye);
        bool found = false;
        // Only trace pixels inside the bounding sphere; the floor and fog stay cheap.
        // Narrow spike slopes need smaller steps to avoid skipping their surfaces.
        float stepScale = 1.0 / (1.1 + 0.76 * u_mid + 5.5 * spikeHeight());
        for (int i = 0; i < 192; ++i) {
            if (hit >= exitDistance) break;
            float d = sphereField(eye + ray * hit - center, radius);
            if (d < 0.001) { found = true; break; }
            hit += d * stepScale;
        }
        if (found) {
            sphere = true;
            distanceToEye = hit;
            vec3 point = eye + ray * hit;
            vec3 normal = sphereNormal(point - center, radius);
            vec3 reflected = reflect(ray, normal);
            float fresnel = pow(1.0 - max(dot(-ray, normal), 0.0), 5.0);
            color = environment(point, reflected) * mix(vec3(0.80, 0.85, 0.93), vec3(1.0), fresnel);
            color += vec3(0.13, 0.16, 0.22) * fresnel;
        }
    }

    vec2 fogP = p * vec2(1.0, 0.82);
    float fog1 = fog_layer(fogP + vec2(-0.20, 0.05), 1.15, vec2(0.020, 0.002), 1.7);
    float fog2 = fog_layer(fogP + vec2(0.30, -0.12), 1.75, vec2(-0.013, 0.005), 7.2);
    float fog3 = fog_layer(fogP + vec2(-0.10, 0.18), 2.55, vec2(0.008, -0.004), 13.4);
    float fog = (fog1 * 0.50 + fog2 * 0.34 + fog3 * 0.22) * u_density;
    fog *= sphere ? 0.25 : 1.0;
    vec3 fogColor = vec3(0.58, 0.60, 0.68) + u_flash * u_pulse * 0.3;
    color = mix(color, fogColor, clamp(fog, 0.0, 0.65));
    color *= 1.0 - smoothstep(0.45, 1.15, length(p)) * 0.35;
    color = color / (vec3(1.0) + color * 0.35);
    fragColor = vec4(pow(max(color, vec3(0.0)), vec3(0.85)), 1.0);
}
