#version 400 core

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;

uniform mat4 u_modelo;
uniform mat4 u_visao;
uniform mat4 u_projecao;

out vec2 f_uv;
out vec3 f_normal;

void main() {
    vec4 posicao = u_modelo * vec4(in_position, 1.0);

    gl_Position = u_projecao * u_visao * posicao;

    f_uv = in_uv;
    f_normal = mat3(transpose(inverse(u_modelo))) * in_normal;
}