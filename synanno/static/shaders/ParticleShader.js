const ParticleShader = {
    uniforms: {
        cameraDistance: { value: 1.0 }, // Unified distance scaling
        particleScale: { value: 1.0 }, // Uniform scaling factor
        sphereTexture: { value: null },
        abstraction_threshold: { value: 0.0 },
    },

    vertexShader: /* glsl */ `
        uniform float cameraDistance;
        uniform float particleScale;
        attribute float radius;
        attribute float grey_out;

        varying vec4 mvPosition;
        varying vec3 vColor;
        varying float vGreyOut;

        void main()
        {
            mvPosition = modelViewMatrix * vec4(position, 1.0);

            float clampedDistance = clamp(cameraDistance, 500.0, 100000.0);

            float t = 1.0 - exp(-((clampedDistance - 500.0) / 15000.0));

            float baseScale = mix(100.0, 1.0, t);

            gl_PointSize = clamp(radius * (baseScale / 100.0), 10.0, 50.0);



            vColor = color;
            vGreyOut = grey_out;

            gl_Position = projectionMatrix * mvPosition;
        }
    `,

    fragmentShader: /* glsl */ `
        uniform sampler2D sphereTexture;
        varying vec3 vColor;
        varying float vGreyOut;

        void main()
        {
            vec3 baseColor = vColor;
            vec2 uv = vec2(gl_PointCoord.x, 1.0 - gl_PointCoord.y);
            vec4 sphereColors = texture2D(sphereTexture, uv);

            if (sphereColors.a < 0.3) discard;

            baseColor = mix(baseColor, baseColor * sphereColors.r, 0.75);
            baseColor += sphereColors.ggg * 0.6;

            float finalAlpha = sphereColors.a;

            if (vGreyOut > 0.5) {
                baseColor = vec3(dot(baseColor, vec3(0.299, 0.587, 0.114)));
                finalAlpha *= 0.3;
            }

            gl_FragColor = vec4(baseColor, finalAlpha);
        }
    `
};

export { ParticleShader };
