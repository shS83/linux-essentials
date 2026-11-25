#version 330 core
uniform sampler2D maximum;
uniform sampler2D previous_peak;
uniform float gain;
uniform float decay;
layout(location=0) out float peak;
void main() {
    peak=max(max(texelFetch(previous_peak,ivec2(0),0).r*decay,
                 log(1.0+texelFetch(maximum,ivec2(0),0).r*gain)),.001);
}
