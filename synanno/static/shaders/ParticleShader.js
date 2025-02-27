const ParticleShader = {
    uniforms: {
        particleScale: { value: 1.0 },
        sphereTexture: { value: null },
        abstraction_threshold: { value: 0.0 },

    },

    vertexShader: /* glsl */ `
        uniform float particleScale;
        attribute float radius;
        attribute float grey_out; // Per-instance attribute

        varying vec4 mvPosition;
        varying vec3 vColor;
        varying float vRadius;
        varying float vGreyOut; // Pass to fragment shader

        void main()
        {
            mvPosition = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = radius * ((particleScale * 2.5) / length(mvPosition.z));

            vColor = color;
            vRadius = radius;
            vGreyOut = grey_out; // Pass grey-out status

            gl_Position = projectionMatrix * mvPosition;
        }
    `,

    fragmentShader: /* glsl */ `
    uniform sampler2D sphereTexture;
    varying vec3 vColor;
    varying vec4 mvPosition;
    varying float vGreyOut; // Get from vertex shader

    void main()
    {
        vec3 baseColor = vColor;
        vec2 uv = vec2(gl_PointCoord.x, 1.0 - gl_PointCoord.y);
        vec4 sphereColors = texture2D(sphereTexture, uv);

        if (sphereColors.a < 0.3) discard;

        baseColor = mix(baseColor, baseColor * sphereColors.r, 0.75);
        baseColor += sphereColors.ggg * 0.6;

        float finalAlpha = sphereColors.a;

        // Apply greying out if vGreyOut is active
        if (vGreyOut > 0.5) {
            baseColor = vec3(dot(baseColor, vec3(0.299, 0.587, 0.114)));
            finalAlpha *= 0.3;
        }

        gl_FragColor = vec4(baseColor, finalAlpha);
    }
`
};

export { ParticleShader };
