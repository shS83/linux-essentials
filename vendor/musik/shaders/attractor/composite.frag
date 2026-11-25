#version 330 core
uniform sampler2D color_image;
in vec2 uv;
out vec4 color;
void main() {
    // Mipmaps supply the original approximately 10-pixel downsampled glow on GPU.
    color=vec4(textureLod(color_image,uv,0.0).rgb+textureLod(color_image,uv,3.321928).rgb,1);
}
