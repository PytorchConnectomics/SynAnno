const SynapseShader = {
    uniforms: {
        sphereTexture: { value: null },
        particleScale: { value: 1.0 },
    },
    vertexShader: `
        uniform float particleScale;
        attribute float radius;
        attribute float alpha;
        varying vec3 vColor;
        varying float vAlpha;

        void main() {
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            float depthScale = -mvPosition.z / 1000.0; // Normalize depth scale
            gl_PointSize = clamp(radius * (particleScale / depthScale), 10.0, 20.0);

            gl_Position = projectionMatrix * mvPosition;

            vColor = color;
            vAlpha = alpha;
        }
    `,
    fragmentShader: `
        uniform sampler2D sphereTexture;
        varying vec3 vColor;
        varying float vAlpha;

        void main() {
            vec2 uv = vec2(gl_PointCoord.x, 1.0 - gl_PointCoord.y);
            vec4 sphereColors = texture2D(sphereTexture, uv);

            if (sphereColors.a < 0.3) discard;

            vec3 baseColor = mix(vColor, vColor * sphereColors.r, 0.75);
            baseColor += sphereColors.ggg * 0.6;

            gl_FragColor = vec4(baseColor, sphereColors.a * vAlpha);
        }
    `,
};

export default SynapseShader;
