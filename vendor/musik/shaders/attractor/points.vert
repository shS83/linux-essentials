#version 330 core
uniform sampler2D particles;
uniform int kind;
uniform vec2 resolution;
uniform float angle;
uniform float tilt;
uniform float zoom;
out float weight;
void main() {
    int side = textureSize(particles,0).x;
    vec3 p = texelFetch(particles,ivec2(gl_VertexID % side,gl_VertexID / side),0).xyz;
    float ca=cos(angle), sa=sin(angle);
    float horizontal=p.x*ca-p.y*sa, vertical=p.x*sa+p.y*ca;
    weight=1.0;
    if (kind >= 2) {
        float z=p.z-(kind==2?25.0:.45), ct=cos(tilt), st=sin(tilt);
        float depth=vertical*ct+z*st;
        vertical=-(z*ct-vertical*st);
        weight=clamp(.8+depth*(kind==2?.02:.25),.25,1.6);
    }
    gl_Position=vec4(horizontal*zoom*2.0/resolution.x,-vertical*zoom*2.0/resolution.y,0,1);
    gl_PointSize=1.0;
}
