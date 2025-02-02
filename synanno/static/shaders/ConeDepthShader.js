/**
 * Compute Cone fragment colors
 */
const ConeDepthShader = {
  uniforms: {
    mNear: { value: 1.0 }, // near clipping plane
    mFar: { value: 1000.0 }, // far clipping plane
    sphereTexture: { value: null }, // texture containing the sphere imposter
  },

  vertexShader: /* glsl */ `

    	attribute float radius;
        attribute float label;

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying float vLabel;

        void main()
        {
            mvPosition = modelViewMatrix * vec4(position, 1.0);
            // Expand quadrilateral perpendicular to both view/screen direction and cone axis
            vec3 cylAxis = (modelViewMatrix * vec4(normal, 0.0)).xyz; // convert cone axis to camera space
            vec3 sideDir = normalize(cross(vec3(0.0,0.0,-1.0), cylAxis));
            mvPosition += vec4(radius * sideDir, 0.0);
            vLabel = label;
            gl_Position = projectionMatrix * mvPosition;
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

            // // We are painting an angled cone onto a flat quad, so depth correction is complicated
            float foreshortening = length(cylAxis) / length(cylAxis.xy); // correct depth for foreshortening
            // foreshortening limit is a tradeoff between overextruded cone artifacts, and depth artifacts
            if (foreshortening > 4.0) foreshortening = 0.9; // hack to not pop out at extreme angles...
            depthScale = radius * foreshortening; // correct depth for foreshortening
        }
`,

  fragmentShader: /* glsl */ `

		uniform sampler2D sphereTexture;
	    uniform float mNear;
	    uniform float mFar;

        varying vec2 sphereUv;
        varying vec4 mvPosition;
        varying float depthScale;
        varying float vLabel;

        void main()
        {
            vec4 sphereColors = texture2D(sphereTexture, sphereUv);
            if (sphereColors.a < 0.3) discard;

            // write fragment depth
            float depth = 1.0 - smoothstep(mNear, mFar, -mvPosition.z);
            gl_FragColor = vec4(vec3(depth), 1.0);
        }
	`,
};

export { ConeDepthShader };
