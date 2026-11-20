#version 400 core

// Mesmo principio do Trabalho 03: amostragem simples da imagem PNG.
in vec2 v_uv;
uniform sampler2D u_textura;
out vec4 out_color;

void main() {
    out_color = texture(u_textura, v_uv);
    if (out_color.a < 0.01) discard;
}
