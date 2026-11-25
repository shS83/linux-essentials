#version 330 core
uniform sampler2D source;
uniform float decay;
layout(location=0) out float density;
void main() { density=texelFetch(source,ivec2(gl_FragCoord.xy),0).r*decay; }
