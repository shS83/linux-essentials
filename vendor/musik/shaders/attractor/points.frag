#version 330 core
in float weight;
layout(location=0) out float density;
void main() { density=weight; }
