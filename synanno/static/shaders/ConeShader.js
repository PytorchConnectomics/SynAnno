const ConeShader = {
    uniforms: {
        sphereTexture: { value: null },
        abstraction_threshold: { value: 0.0 },
        grey_out: { value: 0 },
    },

    vertexShader: /* glsl */ `
        attribute float radius;
        attribute float label;

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying float vLabel;
        varying vec3 vColor;

        void main()
        {
            mvPosition = modelViewMatrix * vec4(position, 1.0);
            vec3 cylAxis = (modelViewMatrix * vec4(normal, 0.0)).xyz;
            vec3 sideDir = normalize(cross(vec3(0.0, 0.0, -1.0), cylAxis));
            mvPosition += vec4(radius * sideDir, 0.0);
            vLabel = label;

            vColor = color;

            gl_Position = projectionMatrix * mvPosition;
        }
    `,

    fragmentShader: /* glsl */ `
        uniform sampler2D sphereTexture;
        uniform float abstraction_threshold;
        uniform int grey_out;

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying float vLabel;
        varying vec3 vColor;

        void main()
        {
            vec3 blendedColor = mix(vColor, vec3(1.0, 1.0, 1.0), 0.15); // Add blending to make surfaces visible
            gl_FragColor = vec4(vColor, 1.0); // Ensure full alpha to render surface
        }
    `,
};

export { ConeShader };
