#version 400 core
layout(location = 0) in vec3 vPosition;
layout(location = 1) in vec3 vNormal;

uniform mat4 u_modelo;
uniform mat4 u_visao;
uniform mat4 u_projecao;
uniform mat3 u_normal;

out vec3 fP;
out vec3 fN;

void main() {
    vec4 pos_camera = u_visao * u_modelo * vec4(vPosition, 1.0);
    gl_Position = u_projecao * pos_camera;
    fP = pos_camera.xyz;
    fN = mat3(u_visao) * u_normal * vNormal;
}
