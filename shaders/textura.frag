#version 400 core

// Iluminacao Blinn-Phong por fragmento, toda no espaco do mundo.
in vec2 f_uv;
in vec3 f_posicao_mundo;
in vec3 f_normal_mundo;

uniform sampler2D u_textura;
uniform vec3 u_camera_posicao;

// Fonte 1: direcional (como luz solar).
uniform vec3 u_direcao_luz;
uniform vec3 u_cor_luz_direcional;

// Fonte 2: pontual, posicionada no centro da estrela.
uniform vec3 u_luz_estrela_posicao;
uniform vec3 u_luz_estrela_cor;
uniform float u_luz_estrela_intensidade;

// Propriedades diferentes para pista, carro e estrela.
uniform vec3 u_ka;
uniform vec3 u_kd;
uniform vec3 u_ks;
uniform float u_alfa;
uniform vec3 u_emissao;

out vec4 outfragcolor;

vec3 contribuicao_blinn_phong(vec3 N, vec3 V, vec3 L,
                              vec3 cor_luz, float fator) {
    float difuso = max(dot(N, L), 0.0);
    float especular = 0.0;
    if (difuso > 0.0) {
        vec3 H = normalize(L + V);
        especular = pow(max(dot(N, H), 0.0), u_alfa);
    }
    return fator * cor_luz * (u_kd * difuso + u_ks * especular);
}

void main() {
    vec4 tex = texture(u_textura, f_uv);
    vec3 N = normalize(f_normal_mundo);
    vec3 V = normalize(u_camera_posicao - f_posicao_mundo);

    // Ambiente + iluminacao direcional.
    vec3 luz = 0.45 * u_ka;
    vec3 L_sol = normalize(u_direcao_luz);
    luz += contribuicao_blinn_phong(N, V, L_sol, u_cor_luz_direcional, 0.8);

    // Distancia do fragmento ate a estrela e atenuacao por distancia.
    vec3 vetor_estrela = u_luz_estrela_posicao - f_posicao_mundo;
    float distancia = length(vetor_estrela);
    vec3 L_estrela = vetor_estrela / max(distancia, 0.0001);
    float atenuacao = 1.0 / (1.0 + 0.65 * distancia + 1.35 * distancia * distancia);
    luz += contribuicao_blinn_phong(N, V, L_estrela, u_luz_estrela_cor,
                                   u_luz_estrela_intensidade * atenuacao);

    // Emissao so na estrela: parece luminosa mesmo na sombra.
    vec3 cor_final = tex.rgb * (luz + u_emissao);
    outfragcolor = vec4(cor_final, tex.a);
}
