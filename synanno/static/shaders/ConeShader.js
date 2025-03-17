const ConeShader = {
    uniforms: {
        sphereTexture: { value: null },
        cameraDistance: { value: 1.0 },
    },

    vertexShader: /* glsl */ `
        uniform float cameraDistance;
        attribute float radius;
        attribute float grey_out;

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying vec3 vColor;
        varying float vGreyOut;

        void main()
        {
            vColor = color;
            vGreyOut = grey_out;

            mvPosition = modelViewMatrix * vec4(position, 1.0);
            vec3 cylAxis = (modelViewMatrix * vec4(normal, 0.0)).xyz;
            vec3 sideDir = normalize(cross(vec3(0.0,0.0,-1.0), cylAxis));

            float clampedDistance = clamp(cameraDistance, 500.0, 100000.0);

            float t = 1.0 - exp(-((clampedDistance - 500.0) / 15000.0));

            float baseScale = mix(120.0, 5.0, t);

            float adjustedRadius = clamp(radius * (baseScale / 100.0), 10.0, 100.0);

            mvPosition += vec4(adjustedRadius * sideDir, 0.0);
            gl_Position = projectionMatrix * mvPosition;

            sphereUv = uv - vec2(0.5, 0.5);
            float q = sideDir.y * sphereUv.y;
            sphereUv.y = sign(q) * sphereUv.y;
            float angle = atan(sideDir.x/sideDir.y);
            float c = cos(angle);
            float s = sin(angle);
            mat2 rotMat = mat2(c, -s, s, c);
            sphereUv = rotMat * sphereUv;
            sphereUv += vec2(0.5, 0.5);

            float foreshortening = length(cylAxis) / length(cylAxis.xy);
            if (foreshortening > 4.0) foreshortening = 0.9;
            depthScale = adjustedRadius * foreshortening;
        }
    `,

    fragmentShader: /* glsl */ `
    uniform sampler2D sphereTexture;
    uniform mat4 projectionMatrix;
    varying vec2 sphereUv;
    varying vec4 mvPosition;
    varying float depthScale;
    varying vec3 vColor;
    varying float vGreyOut;

    void main()
    {
        vec4 sphereColors = texture2D(sphereTexture, sphereUv);
        if (sphereColors.a < 0.3) discard;

        vec3 baseColor = vColor * sphereColors.r;
        vec3 highlightColor = baseColor + sphereColors.ggg;

        float finalAlpha = sphereColors.a;

        if (vGreyOut > 0.5) {
            highlightColor = vec3(dot(highlightColor, vec3(0.299, 0.587, 0.114)));
            finalAlpha *= 0.3;
        }

        gl_FragColor = vec4(highlightColor, finalAlpha);

        float dz = sphereColors.b * depthScale;
        vec4 mvp = mvPosition + vec4(0, 0, dz, 0);
        vec4 clipPos = projectionMatrix * mvp;
        float ndc_depth = clipPos.z / clipPos.w;
        float far = gl_DepthRange.far;
        float near = gl_DepthRange.near;
        float depth = (((far - near) * ndc_depth) + near + far) / 2.0;
        gl_FragDepth = depth;
    }
`,
};

export { ConeShader };
