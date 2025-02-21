const SynapseShader = {
    uniforms: {
        sphereTexture: { value: null },
        particleScale: { value: 1.0 },
    },
    vertexShader: `
        uniform float particleScale;
        attribute float radius;
        varying vec3 vColor;

        void main() {
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = max(radius * ((particleScale * 2.5) / -mvPosition.z), 8.0); // 🔥 Ensure particles are visible
            vColor = color;
            gl_Position = projectionMatrix * mvPosition;
        }
    `,
    fragmentShader: `
        uniform sampler2D sphereTexture;
        varying vec3 vColor;

        void main() {
            vec2 uv = vec2(gl_PointCoord.x, 1.0 - gl_PointCoord.y);
            vec4 sphereColors = texture2D(sphereTexture, uv);

            if (sphereColors.a < 0.3) discard;

            vec3 baseColor = mix(vColor, vColor * sphereColors.r, 0.75);
            baseColor += sphereColors.ggg * 0.6;

            gl_FragColor = vec4(baseColor, sphereColors.a);
        }
    `,
};

export default SynapseShader;
