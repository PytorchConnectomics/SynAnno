const ConeShader = {
    uniforms: {
        sphereTexture: { value: null }, // Texture for 3D shading
    },

    vertexShader: /* glsl */ `
        attribute float radius;
        attribute float grey_out; // Now a per-instance attribute

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying vec3 vColor;
        varying float vGreyOut; // Pass to frprojectionMatrixagment shader

        void main()
        {
            vColor = color; // Keep region-based coloring
            vGreyOut = grey_out; // Pass grey-out status

            mvPosition = modelViewMatrix * vec4(position, 1.0);
            vec3 cylAxis = (modelViewMatrix * vec4(normal, 0.0)).xyz;
            vec3 sideDir = normalize(cross(vec3(0.0,0.0,-1.0), cylAxis));
            mvPosition += vec4(radius * 0.30 * sideDir, 0.0);
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

            // Maintain constant scale
            depthScale = radius;
        }
    `,

    fragmentShader: /* glsl */ `
    uniform sampler2D sphereTexture;
    uniform mat4 projectionMatrix;
    varying vec2 sphereUv;
    varying vec4 mvPosition;
    varying float depthScale;
    varying vec3 vColor;
    varying float vGreyOut; // Get from vertex shader

    void main()
    {
        vec4 sphereColors = texture2D(sphereTexture, sphereUv);
        if (sphereColors.a < 0.3) discard;

        vec3 baseColor = vColor * sphereColors.r;
        vec3 highlightColor = baseColor + sphereColors.ggg;

        float finalAlpha = sphereColors.a;

        // Apply greying out if vGreyOut is active
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
