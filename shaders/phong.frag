#version 400 core
in vec3 fP;
in vec3 fN;

uniform vec4 u_luz;
uniform vec3 u_ka;
uniform vec3 u_kd;
uniform vec3 u_ks;
uniform vec3 u_ia;
uniform vec3 u_id;
uniform vec3 u_is;
uniform float u_alfa;

out vec4 outfragcolor;

void main() {
    vec3 N = normalize(fN);
    vec3 L = normalize(u_luz.xyz - fP);
    vec3 V = normalize(-fP);
    float NdotL = max(dot(N, L), 0.0);
    vec3 ambiente = u_ka * u_ia;
    vec3 difusa = u_kd * u_id * NdotL;
    float brilho = 0.0;
    if (NdotL > 0.0) {
        vec3 R = reflect(-L, N);
        brilho = pow(max(dot(R, V), 0.0), u_alfa);
    }
    vec3 especular = u_ks * u_is * brilho;
    outfragcolor = vec4(ambiente + difusa + especular, 1.0);
}
