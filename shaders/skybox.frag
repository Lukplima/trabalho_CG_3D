
#version 330 core

in vec3 direcao;

uniform sampler2D u_ceu;

out vec4 cor;

const float PI = 3.14159265359;

void main() {

    vec3 dir = normalize(direcao);

    // Converte a direcao 3D em coordenadas da imagem panoramica.
    float u = atan(dir.z, dir.x) / (2.0 * PI) + 0.5;
    float v = asin(clamp(dir.y, -1.0, 1.0)) / PI + 0.5;

    cor = texture(u_ceu, vec2(u, v));
}
