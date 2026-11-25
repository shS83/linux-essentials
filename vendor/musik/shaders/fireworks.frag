#version 330 core
in vec3 v_color;
in float v_life;
in float v_shape;
in float v_angle;
out vec4 fragColor;
uniform float u_time;
void main(){
    vec2 uv=gl_PointCoord*2.0-1.0;
    float a=cos(v_angle),b=sin(v_angle);
    vec2 q=vec2(a*uv.x-b*uv.y,b*uv.x+a*uv.y);
    float radius=length(uv);
    float halo=exp(-radius*radius*7.5)*.32;
    float core=exp(-radius*radius*85.0)*1.65;
    float glow=clamp((halo+core)*v_life,0.0,1.0);
    if(v_shape>1.5 && v_shape<2.5)glow=step(radius,.24)*v_life;
    if(v_shape>2.5){
        // Independent, sharply gated bursts rather than sinusoidal fading.
        // Each sprite receives a stable random phase from v_angle.
        float phase=floor(u_time*47.0+v_angle*31.7);
        float noise=fract(sin(phase*73.13+v_angle*91.17)*43758.5453);
        if(noise<0.55)discard;
        glow=clamp((halo+core)*v_life*1.8,0.0,1.0);
    }
    if(glow<.012)discard;
    fragColor=vec4(v_color*glow,glow);
}
