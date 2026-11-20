#version 400 core

// Adaptado do shader de sprites do Trabalho 03.
in vec2 in_pos;
in vec2 in_uv;
uniform vec2 u_escala;
uniform vec2 u_deslocamento;
out vec2 v_uv;

void main() {
    gl_Position = vec4(in_pos * u_escala + u_deslocamento, 0.0, 1.0);
    v_uv = in_uv;
}
