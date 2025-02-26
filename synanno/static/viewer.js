import SharkViewer, { swcParser, Color, NODE_PARTICLE_IMAGE } from "./SharkViewer/shark_viewer.js";
import SynapseShader from "./shaders/SynapseShader.js";

$(document).ready(function () {

    const neuronReady = $("script[src*='viewer.js']").data("neuron-ready") === true;
    const initialLoad = $("script[src*='viewer.js']").data("initial-load") === true;
    const neuronPath = $("script[src*='viewer.js']").data("neuron-path");
    const neuronSection = $("script[src*='viewer.js']").data("neuron-section");
    const synapseCloudPath = $("script[src*='viewer.js']").data("synapse-cloud-path");

    const $sharkContainerMinimap = $("#shark_container_minimap");

    if (neuronReady) {

        if (initialLoad){
            window.synapseColors = {};
            sessionStorage.removeItem("synapseColors");
            console.log("Initial load, synapseColors cleared.");
        }

        console.log("Neuron data is ready. Initializing viewer...");
        try {
            initializeViewer($sharkContainerMinimap[0]);

            if (neuronPath) {
                loadSwcFile(neuronPath, neuronSection);
            } else {
                console.error("No neuron path provided.");
            }

            if (synapseCloudPath) {
                loadSynapseCloud(synapseCloudPath);
            } else {
                console.error("No synapse cloud path provided.");
            }

            setupWindowResizeHandler($sharkContainerMinimap[0]);

        } catch (error) {
            console.error("Error initializing viewer:", error);
        }
    } else {
        console.log("Neuron data is not available. Viewer will not be initialized.");
    }
});

/**
 * Initializes the SharkViewer instance.
 */
function initializeViewer(sharkContainerMinimap) {
    window.s = new SharkViewer({
        mode: 'particle',
        dom_element: sharkContainerMinimap,
        maxVolumeSize: 1000000,
    });
    console.log("Viewer initialized successfully.");
    s.init();
    s.animate();
}

/**
 * Sets up the window resize handler to adjust the viewer size.
 */
window.setupWindowResizeHandler = function(sharkContainerMinimap) {
    $(window).on('resize', () => onWindowResize(sharkContainerMinimap));
    setTimeout(() => {
        onWindowResize(sharkContainerMinimap);
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
 * Loads and processes a synapse cloud JSON file from the given path.
 *
 * @param {string} jsonPath - The path to the JSON file.
 */
function loadSynapseCloud(jsonPath) {
    fetch(jsonPath)
        .then(response => response.json())
        .then(data => {
            try {

                if (!Array.isArray(data) || data.length % 3 !== 0) {
                    console.error("JSON data is not an Array or length is not a multiple of 3.");
                    return;
                }

                // Load existing synapseColors from sessionStorage or initialize a new one
                window.synapseColors = JSON.parse(sessionStorage.getItem("synapseColors")) || {};

                // Convert data to THREE.Vector3 points
                const points = [];
                for (let i = 0; i < data.length; i += 3) {
                    points.push(new THREE.Vector3(data[i], data[i + 1], data[i + 2]));
                }

                // Create buffer attributes for position, color, and size
                const positions = new Float32Array(points.length * 3);
                const colors = new Float32Array(points.length * 4); // Updated to include alpha
                const sizes = new Float32Array(points.length);

                for (let i = 0; i < points.length; i++) {
                    positions[i * 3] = points[i].x + Math.random() * 50;
                    positions[i * 3 + 1] = points[i].y + Math.random() * 50;
                    positions[i * 3 + 2] = points[i].z + Math.random() * 50;

                    // Assign a default color if not already assigned
                    if (!window.synapseColors[i]) {
                        window.synapseColors[i] = "yellow"; // Default unsure
                    }

                    const colorHex = window.synapseColors[i] === "green" ? 0x00ff00 :
                                     window.synapseColors[i] === "red" ? 0xff0000 : 0xffff00;

                    const color = new THREE.Color(colorHex);
                    colors[i * 4] = color.r;
                    colors[i * 4 + 1] = color.g;
                    colors[i * 4 + 2] = color.b;
                    colors[i * 4 + 3] = window.synapseColors[i] === "yellow" ? 0.2 : 0.9; // Set alpha

                    sizes[i] = 500;
                }

                // Store updated synapseColors in sessionStorage
                sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));

                // Create geometry and add attributes
                const geometry = new THREE.BufferGeometry();
                geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
                geometry.setAttribute("color", new THREE.BufferAttribute(colors, 4)); // Updated to include alpha
                geometry.setAttribute("radius", new THREE.BufferAttribute(sizes, 1));

                // Use SharkViewer's Sphere Texture
                const image = document.createElement("img");
                const sphereTexture = new THREE.Texture(image);
                image.onload = function onload() {
                    sphereTexture.needsUpdate = true;
                };
                image.src = NODE_PARTICLE_IMAGE;

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

                s.scene.add(pointsMesh);
                s.scene.needsUpdate = true;

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

    const skeletonVertex = neuron.children.find(child => child.name === "skeleton-vertex");
    const skeletonEdge = neuron.children.find(child => child.name === "skeleton-edge");

    if (skeletonVertex && skeletonVertex.geometry && skeletonVertex.geometry.attributes.position) {
        const numVertices = skeletonVertex.geometry.attributes.position.count;
        const colors = new Float32Array(numVertices * 3);

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
        const numEdges = skeletonEdge.geometry.attributes.position.count / 2;
        const colors = new Float32Array(numEdges * 6 * 3);

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

window.updateSynapse = function(index, newPosition = null, newColor = null, newSize = null, save_in_session = true) {
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
        positions.needsUpdate = true;
    }

    // Update color if provided
    if (newColor) {
        colors.setXYZ(index, newColor.r, newColor.g, newColor.b);
        colors.needsUpdate = true;

        // Convert THREE.Color to hex string
        let colorLabel = newColor.getHex() === 0x00ff00 ? "green" :
                         newColor.getHex() === 0xff0000 ? "red" : "yellow";

        window.synapseColors[index] = colorLabel;

        if (save_in_session) {
            sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));
        }
    }

    // Update size if provided
    if (newSize !== null) {
        sizes.setX(index, newSize);
        sizes.needsUpdate = true;
    }

    s.render();
};


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
window.onWindowResize = function(sharkContainerMinimap) {
    if (!sharkContainerMinimap) {
        console.error("Shark container not found.");
        return;
    }

    const width = sharkContainerMinimap.clientWidth || window.innerWidth;
    const height = sharkContainerMinimap.clientHeight || window.innerHeight;
    console.log("Resizing viewer to:", width, "x", height);

    if (width > 0 && height > 0) {
        s.camera.aspect = width / height;
        s.camera.updateProjectionMatrix();
        s.renderer.setSize(width, height);
        s.renderer.setPixelRatio(window.devicePixelRatio); // Improves scaling on high-res screens
    }

    s.render();
}
