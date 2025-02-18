const ConeShader = {
    uniforms: {
        sphereTexture: { value: null }, // Texture for 3D shading
        grey_out: { value: 0 }, // Whether to apply greyscale effect
    },

    vertexShader: /* glsl */ `
        attribute float radius;
        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying vec3 vColor;

        void main()
        {
            vColor = color; // Keep region-based coloring

            mvPosition = modelViewMatrix * vec4(position, 1.0);
            // Expand quadrilateral perpendicular to both view/screen direction and cone axis
            vec3 cylAxis = (modelViewMatrix * vec4(normal, 0.0)).xyz; // convert cone axis to camera space
            vec3 sideDir = normalize(cross(vec3(0.0,0.0,-1.0), cylAxis));
            mvPosition += vec4(radius * sideDir, 0.0);
            gl_Position = projectionMatrix * mvPosition;
            // Pass and interpolate color
            // Texture coordinates",
            sphereUv = uv - vec2(0.5, 0.5); // map from [0,1] range to [-.5,.5], before rotation
            // If sideDir is "up" on screen, make sure u is positive'
            float q = sideDir.y * sphereUv.y;
            sphereUv.y = sign(q) * sphereUv.y;
            // rotate texture coordinates to match cone orientation about z
            float angle = atan(sideDir.x/sideDir.y);
            float c = cos(angle);
            float s = sin(angle);
            mat2 rotMat = mat2(c, -s, s, c);
            sphereUv = rotMat * sphereUv;
            sphereUv += vec2(0.5, 0.5); // map back from [-.5,.5] => [0,1]
            // We are painting an angled cone onto a flat quad, so depth correction is complicated
            float foreshortening = length(cylAxis) / length(cylAxis.xy); // correct depth for foreshortening
            // foreshortening limit is a tradeoff between overextruded cone artifacts, and depth artifacts
            if (foreshortening > 4.0) foreshortening = 0.9; // hack to not pop out at extreme angles...
            depthScale = radius * foreshortening; // correct depth for foreshortening
        }
    `,

    fragmentShader: /* glsl */ `
        uniform sampler2D sphereTexture; // Imposter image of sphere
        uniform float abstraction_threshold;
        uniform int grey_out;
        uniform vec3 color;
        uniform mat4 projectionMatrix;

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying vec3 vColor;

        void main()
        {
            vec4 sphereColors = texture2D(sphereTexture, sphereUv);


            if (sphereColors.a < 0.3) discard;

            vec3 baseColor = vColor * sphereColors.r;
            vec3 highlightColor = baseColor + sphereColors.ggg;
            gl_FragColor = vec4(highlightColor, sphereColors.a);

            // Greyscale effect if activated
            if (grey_out == 1) {
                highlightColor = vec3(dot(highlightColor, vec3(0.299, 0.587, 0.114))); // Convert to grayscale
            }

            float dz = sphereColors.b * depthScale;
            vec4 mvp = mvPosition + vec4(0, 0, dz, 0);
            vec4 clipPos = projectionMatrix * mvp;
            float ndc_depth = clipPos.z/clipPos.w;
            float far = gl_DepthRange.far; float near = gl_DepthRange.near;
            float depth = (((far-near) * ndc_depth) + near + far) / 2.0;
            gl_FragDepth = depth;
        }
    `,
};

export { ConeShader };
