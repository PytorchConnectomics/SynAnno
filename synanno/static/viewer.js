import SharkViewer, { swcParser, Color } from "./SharkViewer/shark_viewer.js";
import { nodes_array, edge_array } from "./config.js";

window.onload = () => {
    document.getElementById("swc_input").addEventListener("change", readSwcFile, false);

    try {
        window.s = new SharkViewer({
            mode: 'particle',
            dom_element: document.getElementById('container'),
        });
        s.init();
        s.animate();
    } catch (error) {
        console.error("Error initializing viewer:", error);
    }
};

/**
 * Reads and processes an SWC file selected by the user.
 *
 * @param {Event} e - The event triggered by the file input change.
 * @returns {void}
 *
 * @description
 * This function reads an SWC file using a FileReader, parses the file content,
 * and processes the parsed SWC data. It adds the neuron object to the scene,
 * updates node and edge colors, adjusts the camera, and adds lights to the scene.
 * If any error occurs during the process, an alert is shown to the user.
 *
 * @throws {Error} If there is an error during the SWC file processing.
 */
function readSwcFile(e) {
    const file = e.target.files[0];

    if (!file) {
        alert("No file selected. Please choose an SWC file.");
        return;
    }

    const reader = new FileReader();
    reader.onload = (e2) => {
        try {
            const swcTxt = e2.target.result;
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
                updateNodeAndEdgeColors(s);
                adjustCameraForNeuron(s);
            } else {
                console.warn("Neuron still not found in the scene.");
            }

            addLights(s.scene);
            s.render();
        } catch (error) {
            console.error("Error parsing SWC file:", error);
            alert("An error occurred while processing the SWC file.");
        }
    };
    reader.readAsText(file);
}

/**
 * Updates the colors of nodes and edges in a 3D neuron visualization.
 *
 * @param {Object} viewer - The viewer object containing the scene.
 * @param {Object} neuron_section - The neuron section to be updated.
 * @param {THREE.Color} [color1=Color.blue] - The color to apply to highlighted nodes and edges.
 * @param {THREE.Color} [color2=Color.red] - The color to apply to non-highlighted nodes and edges.
 *
 * @throws Will log an error if the neuron object is not found in the scene.
 *
 * @example
 * // Assuming viewer is a valid viewer object and neuron_section is defined
 * updateNodeAndEdgeColors(viewer, neuron_section, new THREE.Color(0x0000ff), new THREE.Color(0xff0000));
 */
function updateNodeAndEdgeColors(viewer, color1 = Color.blue, color2 = Color.red) {
    const neuron = viewer.scene.getObjectByName('neuron');
    if (!neuron) {
        console.error("Neuron object not found.");
        return;
    }

    console.log("Neuron found! Proceeding with coloring.");
    const nodes = new Set(nodes_array);
    const edges = new Set(edge_array);

    const skeletonVertex = neuron.children.find(child => child.name === "skeleton-vertex");
    const skeletonEdge = neuron.children.find(child => child.name === "skeleton-edge");

    // Update node colors (skeleton-vertex)
    if (skeletonVertex && skeletonVertex.geometry && skeletonVertex.geometry.attributes.position) {
        console.log("Updating node colors...");
        const numVertices = skeletonVertex.geometry.attributes.position.count;
        const colors = new Float32Array(numVertices * 3);
        console.log("Number of numVertices:", numVertices);


        for (let i = 0; i < numVertices; i++) {
            const isHighlighted = nodes.has(i);
            const color = isHighlighted ? new THREE.Color(color1) : new THREE.Color(color2);
            colors.set([color.r, color.g, color.b], i * 3);
        }

        // Assign per-vertex colors
        skeletonVertex.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        skeletonVertex.geometry.attributes.color.needsUpdate = true;

        console.log("Node colors applied successfully.");
    } else {
        console.warn("skeleton-vertex not found or has no geometry.");
    }

    // Update edge colors (skeleton-edge)
    if (skeletonEdge && skeletonEdge.geometry && skeletonEdge.geometry.attributes.position) {
        console.log("Updating edge colors...");
        const numEdges = skeletonEdge.geometry.attributes.position.count / 2; // Each edge has two vertices
        const colors = new Float32Array(numEdges * 6 * 3); // Six edges per node, three color components per vertex

        console.log("Number of edges:", numEdges);
        for (let i = 0; i < numEdges; i++) {
            const isHighlighted = edges.has(i);
            const color = isHighlighted ? new THREE.Color(color1) : new THREE.Color(color2);

            // Assign the same color to all six vertices of the edge
            for (let j = 0; j < 6; j++) {
                colors.set([color.r, color.g, color.b], (i * 6 + j) * 3);
            }
        }

        // Assign per-edge colors
        skeletonEdge.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        skeletonEdge.geometry.attributes.color.needsUpdate = true;

        console.log("Edge colors applied successfully.");
    } else {
        console.warn("skeleton-edge not found or has no geometry.");
    }
    viewer.render();
}

/**
 * Adjusts the camera position and settings to focus on a neuron object in the scene.
 *
 * @param {Object} viewer - The viewer object containing the scene and camera.
 * @param {THREE.Scene} viewer.scene - The scene containing the objects.
 * @param {THREE.Camera} viewer.camera - The camera to be adjusted.
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
    const distance = (maxDim / 2) / Math.tan(fov / 2);

    viewer.camera.position.set(center.x, center.y, center.z + distance * 0.3);
    viewer.camera.lookAt(center);
    viewer.camera.near = distance / 10;
    viewer.camera.far = distance * 10;
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
