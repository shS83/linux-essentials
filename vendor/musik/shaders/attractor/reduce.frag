#version 330 core
uniform sampler2D source;
layout(location=0) out float maximum;
void main() {
    ivec2 base=ivec2(gl_FragCoord.xy)*2, size=textureSize(source,0);
    maximum=0.0;
    for(int y=0;y<2;++y) for(int x=0;x<2;++x) {
        ivec2 p=base+ivec2(x,y);
        if(all(lessThan(p,size))) maximum=max(maximum,texelFetch(source,p,0).r);
    }
}
