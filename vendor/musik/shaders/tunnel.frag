#version 330 core

uniform vec2 uResolution;
uniform float uTime;
uniform float uFlash;
uniform vec3 uCamera;
uniform vec3 uForward;
uniform vec3 uRight;
uniform vec3 uUp;
uniform int uPaletteFrom;
uniform int uPaletteTo;
uniform float uPaletteMix;
out vec4 fragColor;

const float PI = 3.14159265358979323846;

vec3 hsv(float hue, float saturation, float value) {
    vec3 rgb = clamp(abs(fract(hue+vec3(0.0, 2.0/3.0, 1.0/3.0))*6.0-3.0)-1.0,
                     0.0, 1.0);
    return value*mix(vec3(1.0), rgb, saturation);
}

vec3 palette(int mode, float hue, float light) {
    if (mode == 0) return vec3(light);
    if (mode == 1) return hsv(hue, 0.87, light);
    float h = mode==2 ? 0.635 : mode==3 ? 0.35 : mode==4 ? 0.155 : 0.005;
    // Yksivärisessä paletissa vaaleat harjanteet saavat hieman valkoista.
    return hsv(h, 0.96-0.18*pow(light, 3.0), light);
}

void main() {
    // Korkeus toimii molempien akselien mittana: ympyrä pysyy pyöreänä
    // myös leveässä ikkunassa. 0.72 vastaa noin 72 asteen pystynäkökenttää.
    vec2 screen = (2.0*gl_FragCoord.xy-uResolution)/uResolution.y;
    vec3 ray = normalize(uForward + 0.72*(screen.x*uRight + screen.y*uUp));

    // Säde: p = kamera + t*suunta. Seinällä p.x²+p.y²=1.
    // Sijoittamisesta saadaan toisen asteen yhtälö a*t²+2*b*t+c=0.
    // Kamera on putken sisällä, joten positiivinen juuri osuu seinään.
    float a = dot(ray.xy, ray.xy);
    float b = dot(uCamera.xy, ray.xy);
    float c = dot(uCamera.xy, uCamera.xy)-1.0;
    if (a < 0.000001) { fragColor=vec4(vec3(uFlash),1); return; }
    float root = sqrt(max(0.0, b*b-a*c));
    // Tämä muoto välttää lähes samojen lukujen vähentämisen, kun b>0.
    float distance = b>0.0 ? -c/(b+root) : (-b+root)/a;
    vec3 hit = uCamera + ray*min(distance, 160.0);
    float angle = atan(hit.y, hit.x);
    float z = hit.z;

    // Kulman kertoimet ovat kokonaislukuja. Kuvio kohtaa itsensä
    // saumattomasti kohdassa -pi/+pi, vaikka kamera kiertää sen ympäri.
    float warp = 0.70*sin(3.0*angle+z*0.62+uTime*0.31)
               + 0.32*sin(7.0*angle-z*0.39-uTime*0.24);
    float ringsPhase = z*3.2 + 1.05*sin(5.0*angle+uTime*0.35) + warp;
    float ribsPhase = angle*12.0 + z*0.83 + 0.65*sin(z*0.47-uTime*0.23);

    // Kaukana yksi pikseli voi kattaa monta raitaa. fwidth kertoo
    // pikselin vaihe-eron; vaimennus ehkäisee moirékuvioita ja vilinää.
    float ringFilter = 1.0-smoothstep(0.45, 3.0, fwidth(ringsPhase));
    // atan hyppää saumassa +pi:stä -pi:hin. Kulmaeron kääriminen
    // estää suodatinta piirtämästä näkyvää viivaa pitkin tätä saumaa.
    vec2 angleDelta = mod(vec2(dFdx(angle),dFdy(angle))+PI,2.0*PI)-PI;
    vec2 zDelta = vec2(dFdx(z),dFdy(z));
    vec2 ribDelta = 12.0*angleDelta +
        (0.83+0.65*0.47*cos(z*0.47-uTime*0.23))*zDelta;
    float ribFilter = 1.0-smoothstep(0.45,3.0,abs(ribDelta.x)+abs(ribDelta.y));
    float rings = sin(ringsPhase)*ringFilter;
    float ribs = sin(ribsPhase)*ribFilter;
    float plasma = sin(angle*4.0-z*1.35+warp+uTime*0.27);
    float field = clamp(0.49+0.25*rings+0.15*ribs+0.10*plasma, 0.0, 1.0);
    float contrast = 1.15+0.55*(0.5+0.5*sin(uTime*0.21));
    float light = 0.035+0.965*pow(field, contrast);

    // Sumennuksen sijaan kaukaiset seinät häipyvät pimeään.
    // Näin tunnelin pakopiste säilyy rauhallisena eikä sahalaita vilku.
    float fog = exp(-0.032*distance)*(1.0-smoothstep(48.0, 85.0, distance));
    float hue = angle/(2.0*PI)+z*0.045+0.16*plasma+uTime*0.025;
    vec3 color = mix(palette(uPaletteFrom,hue,light),
                     palette(uPaletteTo,hue,light), uPaletteMix)*fog;
    fragColor = vec4(mix(color, vec3(1.0), uFlash), 1.0);
}
