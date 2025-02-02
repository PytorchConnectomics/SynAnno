const ParticleShader = {
    uniforms: {
        particleScale: { value: 1.0 },
        sphereTexture: { value: null },
        abstraction_threshold: { value: 0.0 },
        grey_out: { value: 0 },
    },

    vertexShader: /* glsl */ `
        uniform float particleScale;
        attribute float radius;
        attribute float label;

        varying float vLabel;
        varying vec4 mvPosition;
        varying vec3 vColor;

        void main()
        {
            vLabel = label;
            mvPosition = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = radius * ((particleScale * 2.5) / length(mvPosition.z));

            vColor = color;

            gl_Position = projectionMatrix * mvPosition;
        }
    `,

    fragmentShader: /* glsl */ `
        varying vec3 vColor;

        void main()
        {
            vec3 myColor = vColor;
            gl_FragColor = vec4(myColor, 1.0);
        }
    `,
};

export { ParticleShader };
