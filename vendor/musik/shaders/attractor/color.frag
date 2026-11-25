#version 330 core
uniform sampler2D density;
uniform sampler2D peak;
uniform float gain;
uniform float phase;
uniform int palette;
layout(location=0) out vec4 color;
void main() {
    float value=log(1.0+texelFetch(density,ivec2(gl_FragCoord.xy),0).r*gain);
    float t=clamp(value/max(.001,texelFetch(peak,ivec2(0),0).r),0.0,1.0);
    t=floor(t*255.0)/255.0;
    vec3 frequency=vec3(1), offset=vec3(0,.33,.67);
    if(palette==1){frequency=vec3(1,1,.5);offset=vec3(.8,.9,.3);}
    if(palette==2){frequency=vec3(1,.7,.4);offset=vec3(0,.15,.2);}
    if(palette==3){frequency=vec3(2,1,0);offset=vec3(.5,.2,.25);}
    color=vec4((.5+.5*cos(6.28318530718*(t*frequency+offset+phase)))*pow(t,.75),1);
}
