
#version 330 core

in vec3 in_posicao;

uniform mat4 u_visao;
uniform mat4 u_projecao;

out vec3 direcao;

void main() {

    direcao = in_posicao;

    vec4 posicao = u_projecao * u_visao * vec4(in_posicao, 1.0);

    // Coloca o skybox na profundidade maxima.
    gl_Position = posicao.xyww;
}
