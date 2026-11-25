#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in float a_size;
layout(location=2) in float a_life;
layout(location=3) in vec3 a_color;
layout(location=4) in float a_shape;
layout(location=5) in float a_angle;
uniform vec2 u_resolution;
out vec3 v_color;
out float v_life;
out float v_shape;
out float v_angle;
void main(){
    vec2 ndc=(a_pos/u_resolution)*2.0-1.0;
    gl_Position=vec4(ndc.x,-ndc.y,0.0,1.0);
    gl_PointSize=a_size;
    v_color=a_color;v_life=a_life;v_shape=a_shape;v_angle=a_angle;
}
