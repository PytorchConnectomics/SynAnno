import SharkViewer, { swcParser, Color, NODE_PARTICLE_IMAGE } from "./SharkViewer/shark_viewer.js";
import SynapseShader from "./shaders/SynapseShader.js";

window.onload = () => {
    const neuronReady = $("script[src*='viewer.js']").data("neuron-ready");
    const neuronPath = $("script[src*='viewer.js']").data("neuron-path");
    const neuronSection = $("script[src*='viewer.js']").data("neuron-section");
    const synapseCloudPath = $("script[src*='viewer.js']").data("synapse-cloud-path");

    if (neuronReady) {
        console.log("Neuron data is ready. Initializing viewer...");
        try {
            initializeViewer();

            if (neuronPath) {
                loadSwcFile(neuronPath, neuronSection);
            } else {
                console.error("No neuron path provided.");
            }

            if (synapseCloudPath) {
                setTimeout(() => loadSynapseCloud(synapseCloudPath), 1500);
            } else {
                console.error("No synapse cloud path provided.");
            }

            // waite 10 seconds and then color the first 200 synapses green
            setTimeout(() => {
                for (let i = 0; i < 800; i++) {
                    updateSynapse(i, null, new THREE.Color(0x00ff00), 1000);
                }
            }, 10000);

            setupWindowResizeHandler();

        } catch (error) {
            console.error("Error initializing viewer:", error);
        }
    } else {
        console.log("Neuron data is not available. Viewer will not be initialized.");
    }
};

/**
 * Initializes the SharkViewer instance.
 */
function initializeViewer() {
    window.s = new SharkViewer({
        mode: 'particle',
        dom_element: document.getElementById('shark_container'),
        maxVolumeSize: 1000000,
    });
    console.log("Viewer initialized successfully.");
    s.init();
    s.animate();
}

/**
 * Sets up the window resize handler to adjust the viewer size.
 */
function setupWindowResizeHandler() {
    window.addEventListener('resize', onWindowResize, false);
    setTimeout(() => {
        onWindowResize();
        s.render(); // Force a re-render
    }, 100); // Delay to allow layout updates
}

/**
 * Loads and processes an SWC file from the given path.
 *
 * @param {string} swcPath - The path to the SWC file.
 * @param {Array} neuronSection - The neuron sections to be highlighted.
 */
function loadSwcFile(swcPath, neuronSection) {
    fetch(swcPath)
        .then(response => response.text())
        .then(swcTxt => {
            try {
                let swc = swcParser(swcTxt);

                if (!swc || Object.keys(swc).length === 0) {
                    console.error("SWC parsing failed. The SWC object is empty.");
                    return;
                }

                console.log("Parsed SWC data:", swc);
                s.swc = swc;

                const neuronData = s.loadNeuron('neuron', 'red', swc, true, false, true);
                const neuronObject = neuronData[0];

                if (neuronObject && neuronObject.isObject3D) {
                    s.scene.add(neuronObject);
                    console.log("Neuron object successfully added to the scene.");
                } else {
                    console.warn("Neuron object is missing or invalid.");
                }

                const neuron = s.scene.getObjectByName('neuron');

                if (neuron) {
                    console.log("Neuron found! Proceeding with color update.");
                    updateNodeAndEdgeColors(s, neuronSection, neuronSection);
                    setTimeout(() => adjustCameraForNeuron(s), 500); // Ensure camera resets after neuron is loaded
                } else {
                    console.warn("Neuron still not found in the scene.");
                }

                addLights(s.scene);
                s.render();
            } catch (error) {
                console.error("Error parsing SWC file:", error);
                alert("An error occurred while processing the SWC file.");
            }
        })
        .catch(error => {
            console.error("Error fetching SWC file:", error);
            alert("An error occurred while fetching the SWC file.");
        });
}

/**
 * Loads a synapse cloud JSON file and applies a custom shader.
 */
function loadSynapseCloud(jsonPath) {
    fetch(jsonPath)
        .then(response => response.json())
        .then(data => {
            try {
                console.log("Synapse Cloud Data length:", data.length);

                if (!Array.isArray(data) || data.length % 3 !== 0) {
                    console.error("JSON data is not an Array or length is not a multiple of 3.");
                    return;
                }

                // Convert data to THREE.Vector3 points
                const points = [];
                for (let i = 0; i < data.length; i += 3) {
                    points.push(new THREE.Vector3(data[i], data[i + 1], data[i + 2]));
                }

                // Create buffer attributes for position, color, and size
                const positions = new Float32Array(points.length * 3);
                const colors = new Float32Array(points.length * 3);
                const sizes = new Float32Array(points.length);

                for (let i = 0; i < points.length; i++) {
                    // Store positions, adding a random offset to each point to move them out of the skeleton
                    positions[i * 3] = points[i].x + Math.random() * 50;
                    positions[i * 3 + 1] = points[i].y + Math.random() * 50;
                    positions[i * 3 + 2] = points[i].z + Math.random() * 50;

                    // Assign random colors for better visualization
                    // initially color all synapses yellow
                    const color = new THREE.Color(0xffff00);
                    colors[i * 3] = color.r;
                    colors[i * 3 + 1] = color.g;
                    colors[i * 3 + 2] = color.b;

                    sizes[i] = 500;
                }

                // Create geometry and add attributes
                const geometry = new THREE.BufferGeometry();
                geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
                geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
                geometry.setAttribute("radius", new THREE.BufferAttribute(sizes, 1));

                // Use SharkViewer's Sphere Texture
                const image = document.createElement("img");
                const sphereTexture = new THREE.Texture(image);

                image.onload = function onload() {
                    sphereTexture.needsUpdate = true;
                    console.log("Sphere texture loaded and updated.");
                };

                image.src = NODE_PARTICLE_IMAGE; // Load texture from SharkViewer

                // Set the sphere texture uniform
                SynapseShader.uniforms["sphereTexture"].value = sphereTexture;

                // Define shader material using imposter spheres
                const material = new THREE.ShaderMaterial({
                    uniforms: SynapseShader.uniforms,
                    vertexShader: SynapseShader.vertexShader,
                    fragmentShader: SynapseShader.fragmentShader,
                    transparent: true,
                    vertexColors: true,
                });

                // Create points and add to the scene
                const pointsMesh = new THREE.Points(geometry, material);
                pointsMesh.name = "synapse-cloud";

                console.log("Adding particle system to scene.");
                s.scene.add(pointsMesh);
                s.scene.needsUpdate = true;
                console.log("Particle system added:", pointsMesh);

                // Adjust camera to ensure visibility
                adjustCameraForNeuron(s);

                s.render();
                console.log("Synapse cloud successfully added.");
            } catch (error) {
                console.error("Error processing synapse cloud:", error);
            }
        })
        .catch(error => {
            console.error("Error fetching synapse cloud data:", error);
        });
}

/**
 * Updates the colors of nodes and edges in a 3D neuron visualization.
 *
 * @param {Object} viewer - The viewer object containing the scene.
 * @param {Array} nodes_array - The array of nodes to be updated.
 * @param {Array} edge_array - The array of edges to be updated.
 * @param {Array} sectionColors - The colors to apply to the sections.
 */
function updateNodeAndEdgeColors(viewer, nodes_array, edge_array, sectionColors) {
    const neuron = viewer.scene.getObjectByName('neuron');
    if (!neuron) {
        console.error("Neuron object not found.");
        return;
    }

    if (!sectionColors) {
        sectionColors = generateSectionColors(nodes_array.length);
    }

    console.log("Neuron found! Proceeding with coloring.");
    const skeletonVertex = neuron.children.find(child => child.name === "skeleton-vertex");
    const skeletonEdge = neuron.children.find(child => child.name === "skeleton-edge");

    if (skeletonVertex && skeletonVertex.geometry && skeletonVertex.geometry.attributes.position) {
        console.log("Updating node colors...");
        const numVertices = skeletonVertex.geometry.attributes.position.count;
        const colors = new Float32Array(numVertices * 3);
        console.log("Number of numVertices:", numVertices);

        nodes_array.forEach((nodeGroup, index) => {
            const color = new THREE.Color(sectionColors[index] || 0xffffff);
            nodeGroup.forEach(nodeIndex => {
                if (nodeIndex < numVertices) {
                    colors.set([color.r, color.g, color.b], nodeIndex * 3);
                }
            });
        });

        skeletonVertex.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        skeletonVertex.geometry.attributes.color.needsUpdate = true;
        console.log("Node colors applied successfully.");
    } else {
        console.warn("skeleton-vertex not found or has no geometry.");
    }

    if (skeletonEdge && skeletonEdge.geometry && skeletonEdge.geometry.attributes.position) {
        console.log("Updating edge colors...");
        const numEdges = skeletonEdge.geometry.attributes.position.count / 2;
        const colors = new Float32Array(numEdges * 6 * 3);
        console.log("Number of edges:", numEdges);

        edge_array.forEach((edgeGroup, index) => {
            const color = new THREE.Color(sectionColors[index] || 0xffffff);
            edgeGroup.forEach(edgeIndex => {
                if (edgeIndex < numEdges) {
                    for (let j = 0; j < 6; j++) {
                        colors.set([color.r, color.g, color.b], (edgeIndex * 6 + j) * 3);
                    }
                }
            });
        });

        skeletonEdge.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        skeletonEdge.geometry.attributes.color.needsUpdate = true;
        console.log("Edge colors applied successfully.");
    } else {
        console.warn("skeleton-edge not found or has no geometry.");
    }

    viewer.render();
}

function updateSynapse(index, newPosition = null, newColor = null, newSize = null) {
    const pointsMesh = s.scene.getObjectByName("synapse-cloud");
    if (!pointsMesh) {
        console.error("Synapse cloud not found in the scene.");
        return;
    }

    const geometry = pointsMesh.geometry;
    const positions = geometry.getAttribute("position");
    const colors = geometry.getAttribute("color");
    const sizes = geometry.getAttribute("radius");

    if (index < 0 || index >= positions.count) {
        console.error("Invalid synapse index.");
        return;
    }

    // Update position if provided
    if (newPosition) {
        positions.setXYZ(index, newPosition.x, newPosition.y, newPosition.z);
        // Mark attribute as needing an update
        positions.needsUpdate = true;
    }

    // Update color if provided
    if (newColor) {
        colors.setXYZ(index, newColor.r, newColor.g, newColor.b);
        // Mark attribute as needing an update
        colors.needsUpdate = true;
    }

    // Update size if provided
    if (newSize !== null) {
        sizes.setX(index, newSize);
        // Mark attribute as needing an update
        sizes.needsUpdate = true;
    }

    s.render();
    console.log(`Synapse at index ${index} updated.`);
}

/**
 * Adjusts the camera position and settings to focus on a neuron object in the scene.
 *
 * @param {Object} viewer - The viewer object containing the scene and camera.
 */
function adjustCameraForNeuron(viewer) {
    const neuron = viewer.scene.getObjectByName('neuron');
    if (!neuron) {
        console.error("Neuron object not found in scene.");
        return;
    }

    const boundingBox = new THREE.Box3().setFromObject(neuron);
    const size = boundingBox.getSize(new THREE.Vector3());
    const center = boundingBox.getCenter(new THREE.Vector3());

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = viewer.camera.fov * (Math.PI / 180);
    let distance = (maxDim / 2) / Math.tan(fov / 2);

    if (distance < 50) distance = 50; // Prevent too-close zoom
    if (distance > 1000000) distance = 1000000; // Prevent excessive zoom-out

    console.log("Adjusting camera. Distance:", distance, "Bounding box size:", size);

    viewer.camera.position.set(center.x, center.y, center.z + distance * 0.5);
    viewer.camera.lookAt(center);
    viewer.camera.near = 1;
    viewer.camera.far = distance * 2;
    viewer.camera.updateProjectionMatrix();
}

/**
 * Adds ambient and directional lights to the given scene if they do not already exist.
 *
 * @param {THREE.Scene} scene - The scene to which the lights will be added.
 */
function addLights(scene) {
    if (!scene.getObjectByName("ambient-light")) {
        const ambientLight = new THREE.AmbientLight(Color.white, 1.0);
        ambientLight.name = "ambient-light";
        scene.add(ambientLight);
    }
    if (!scene.getObjectByName("directional-light")) {
        const directionalLight = new THREE.DirectionalLight(Color.grey, 0.4);
        directionalLight.name = "directional-light";
        scene.add(directionalLight);
    }
}

/**
 * Generates an array of high-contrast colors for a given number of sections.
 * The colors are spread across the full hue spectrum for better distinction.
 *
 * @param {number} numSections - The number of sections to generate colors for.
 * @returns {THREE.Color[]} An array of THREE.Color objects representing the colors for each section.
 */
function generateSectionColors(numSections) {
    const colors = [];
    for (let i = 0; i < numSections; i++) {
        const hue = (i / numSections) * 1.0;
        const saturation = 1.0;
        const lightness = 0.4;
        colors.push(new THREE.Color().setHSL(hue, saturation, lightness));
    }
    return colors;
}

/**
 * Handles window resize events to adjust the viewer's size and camera aspect ratio.
 */
function onWindowResize() {
    const container = document.getElementById('shark_container');
    if (!container) {
        console.error("Shark container not found.");
        return;
    }

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;
    console.log("Resizing viewer to:", width, "x", height);

    if (width > 0 && height > 0) {
        s.camera.aspect = width / height;
        s.camera.updateProjectionMatrix();
        s.renderer.setSize(width, height);
        s.renderer.setPixelRatio(window.devicePixelRatio); // Improves scaling on high-res screens
    }

    s.render();
}
