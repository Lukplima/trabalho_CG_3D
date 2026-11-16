#version 400 core

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;

uniform mat4 u_modelo;
uniform mat4 u_visao;
uniform mat4 u_projecao;

out vec2 f_uv;
out vec3 f_posicao_mundo;
out vec3 f_normal_mundo;

void main() {
    vec4 posicao_mundo = u_modelo * vec4(in_position, 1.0);
    gl_Position = u_projecao * u_visao * posicao_mundo;
    f_uv = in_uv;
    f_posicao_mundo = posicao_mundo.xyz;
    // Matriz normal = inversa transposta da parte linear da matriz de modelo.
    f_normal_mundo = transpose(inverse(mat3(u_modelo))) * in_normal;
}
