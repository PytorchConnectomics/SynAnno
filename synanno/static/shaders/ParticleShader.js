const ParticleShader = {
    uniforms: {
        particleScale: { value: 1.0 },
        sphereTexture: { value: null }, // Sphere texture for imposter shading
        abstraction_threshold: { value: 0.0 },
        grey_out: { value: 0 },
    },

    vertexShader: /* glsl */ `
        uniform float particleScale;
        attribute float radius;

        varying vec4 mvPosition;
        varying vec3 vColor;
        varying float vRadius;

        void main()
        {
            mvPosition = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = radius * ((particleScale * 2.5) / length(mvPosition.z));

            vColor = color;
            vRadius = radius;

            gl_Position = projectionMatrix * mvPosition;
        }
    `,

    fragmentShader: /* glsl */ `
        uniform sampler2D sphereTexture; // Sphere imposter texture

        varying vec3 vColor;
        varying vec4 mvPosition;
        varying float vRadius;

        void main()
        {
            vec3 baseColor = vColor;

            // Check if texture is available, else use color directly
            vec2 uv = vec2(gl_PointCoord.x, 1.0 - gl_PointCoord.y);
            vec4 sphereColors = texture2D(sphereTexture, uv);

            if (sphereColors.a < 0.3) discard; // Remove invisible corners

            // Increase influence of sphere texture shading
            baseColor = mix(baseColor, baseColor * sphereColors.r, 0.75); // Larger number = more shading
            baseColor += sphereColors.ggg * 0.6; // Larger number = stronger highlights

            gl_FragColor = vec4(baseColor, sphereColors.a);
        }
    `,
};

export { ParticleShader };
