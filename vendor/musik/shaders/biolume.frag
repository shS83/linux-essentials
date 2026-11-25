#version 330 core
in vec2 uv;
out vec4 fragColor;
uniform vec2 u_resolution;
uniform float u_time, u_bass, u_treble, u_pulse;
uniform vec4 u_cells[8]; // xy: centers; z: radius; w: energy
uniform vec4 u_flies[48];
uniform vec3 u_cellColors[8]; // pigment accumulated from captured fireflies
uniform vec4 u_glows[16]; // xy: capture position, z: fly color (4 for merge), w: lifetime
uniform vec4 u_fragments[72]; // two independent groups of 36 tiny cells
uniform vec3 u_burstColors[2];
uniform vec4 u_sparks[64]; // xy: position, z: size, w: remaining life

float softUnion(float a,float b,float k){
    float h=max(k-abs(a-b),0.0)/k;
    return min(a,b)-h*h*k*.25;
}
float noise(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
vec3 flyTint(int kind){
    if(kind==0)return vec3(.08,.84,1.0);
    if(kind==1)return vec3(.18,.96,.32);
    if(kind==2)return vec3(1.0,.82,.12);
    return vec3(1.0,.18,.12);
}
void main(){
    float unit=min(u_resolution.x,u_resolution.y);
    vec2 p=(gl_FragCoord.xy-.5*u_resolution)/unit;
    float t=u_time;
    vec3 background=mix(vec3(.012,.006,.045),vec3(.045,.008,.065),smoothstep(-.55,.55,p.y));
    background+=.008*vec3(.2,.4,.8)*sin(p.y*13.+t*.2);
    float sdf=5.0,core=0.0,halo=0.0,sheen=0.0;
    vec3 fragmentLight=vec3(0.0);
    vec3 sparkLight=vec3(0.0);
    float pixel=1.0/unit;
    for(int i=0;i<8;i++){
        vec4 c=u_cells[i];
        vec2 v=p-c.xy;
        float a=atan(v.y,v.x);
        // Slow, low-amplitude breathing keeps the membrane round and soft.
        float deform=c.z*(.018*sin(3.*a+t*.48+float(i)*1.7)
                         +.008*sin(5.*a-t*.31+float(i)));
        float radius=c.z*(1.+.07*u_bass+.24*u_pulse)+deform;
        float d=length(v)-radius;
        sdf=softUnion(sdf,d,.022);
        core+=c.w*exp(-dot(v,v)/(radius*radius*.70));
        halo+=.04*exp(-abs(d)*22.);
        sheen+=exp(-d*d/.00012)*max(0.,dot(v/max(length(v),.0001),vec2(-.6,.8)));
    }
    for(int i=0;i<72;i++){
        vec4 f=u_fragments[i];
        if(f.w<=0.0)continue;
        vec2 v=p-f.xy;
        float radius=max(f.z,pixel*.65);
        float spread=max(radius*2.4,pixel*2.5);
        if(abs(v.x)>spread*3.0 || abs(v.y)>spread*3.0)continue;
        float r2=dot(v,v);
        float d=sqrt(r2);
        float coverage=1.0-smoothstep(radius-pixel*.7,radius+pixel*.7,d);
        float rim=exp(-pow((d-radius)/max(pixel*1.2,radius*.18),2.0));
        float glow=exp(-r2/(spread*spread));
        float alpha=smoothstep(0.0,.25,f.w);
        vec3 tint=u_burstColors[i/36]*(.92+.08*sin(float(i)*2.17));
        fragmentLight+=tint*alpha*(coverage*.58+rim*.22+glow*.16);
    }
    for(int i=0;i<64;i++){
        vec4 s=u_sparks[i];
        if(s.w<=0.0)continue;
        vec2 v=p-s.xy;
        float spread=max(s.z*3.0,pixel*3.0);
        if(abs(v.x)>spread*3.0 || abs(v.y)>spread*3.0)continue;
        float r2=dot(v,v);
        float coreSpark=exp(-r2/max(s.z*s.z,pixel*pixel*.8));
        float glowSpark=exp(-r2/(spread*spread));
        float alpha=smoothstep(0.0,.28,s.w);
        vec3 tint=i%3==0?vec3(1.0,.68,.30):(i%3==1?vec3(.55,.85,1.0):vec3(1.0));
        sparkLight+=tint*alpha*(coreSpark*1.15+glowSpark*.22);
    }
    float membrane=exp(-abs(sdf)*125.);
    float body=1.-smoothstep(-.012,.012,sdf);
    float translucent=body*(.18+.035*sin(3.*p.x+2.*p.y+t*.22));
    vec3 color=background;
    vec3 pigments=vec3(0.0);
    float pigmentWeight=0.0;
    for(int i=0;i<8;i++){
        vec2 d=p-u_cells[i].xy;
        float w=exp(-dot(d,d)/max(.0001,u_cells[i].z*u_cells[i].z*.72));
        pigments+=u_cellColors[i]*w;
        pigmentWeight+=w;
    }
    pigments/=max(.0001,pigmentWeight);
    color+=pigments*translucent*.70;
    color+=pigments*membrane*.38;
    color+=pigments*(body*.06+membrane*.24)*u_pulse;
    color+=vec3(.38,.52,.64)*sheen*.085;
    color+=vec3(.04,.12,.18)*halo;
    // Captured color spreads through the translucent cell.
    vec3 bioLight=core*.16*pigments;
    for(int i=0;i<16;i++){
        vec4 g=u_glows[i];
        float age=1.-g.w;
        vec2 d=p-g.xy;
        float spread=.014+age*.13;
        vec3 tint=g.z>3.5?pigments:flyTint(int(g.z));
        bioLight+=tint*g.w*.9*exp(-dot(d,d)/(spread*spread));
        // A soft wave travelling over the connected cell interior.
        float ring=abs(length(d)-age*.21);
        bioLight+=tint*g.w*.13*exp(-ring*ring/.00007);
    }
    color+=body*bioLight*.70;
    color+=membrane*bioLight*.25;
    // Four equally represented firefly colors, with bright cores and soft halos.
    vec3 flyLight=vec3(0.);
    for(int i=0;i<48;i++){
        vec4 f=u_flies[i];
        vec2 d=p-f.xy;
        float r2=dot(d,d);
        float flicker=.70+.30*sin(t*9.+f.z*5.);
        float glow=exp(-r2/.00020)*flicker;
        float dotlight=exp(-r2/.000010)*flicker;
        vec3 tint=flyTint(i%4);
        flyLight+=glow*tint*.45+dotlight*(tint*1.6+vec3(.18));
    }
    color+=flyLight;
    color+=fragmentLight+sparkLight;
    // Faint, animated iridescence over the membrane.
    color+=membrane*.06*vec3(.5+.5*sin(t*.7+p.y*28.),.22,.8);
    color=1.-exp(-color*1.1); // gentle tone mapping
    color=pow(max(color,vec3(0.)),vec3(.90));
    fragColor=vec4(color,1.);
}
