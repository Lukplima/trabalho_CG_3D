#version 400 core

in vec2 f_uv;
in vec3 f_normal;

uniform sampler2D u_textura;

out vec4 outfragcolor;

void main() {
    vec3 normal = normalize(f_normal);
    vec3 luz = normalize(vec3(-0.5, 1.0, 1.0));

    float iluminacao = max(dot(normal, luz), 0.0);
    iluminacao = 0.25 + iluminacao * 0.75;

    vec4 cor = texture(u_textura, f_uv);

    outfragcolor = vec4(cor.rgb * iluminacao, cor.a);
}