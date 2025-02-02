import SharkViewer, { swcParser, Color } from "./SharkViewer/shark_viewer.js";

import { single_branch } from "./config.js";

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
 *
 * @description
 * This function handles the reading of an SWC file using the FileReader API.
 * It parses the SWC file content, loads the neuron data into the scene,
 * and updates the scene with the neuron object. It also adjusts the camera
 * and updates node and edge colors.
 *
 * @throws Will alert the user if no file is selected or if an error occurs during file processing.
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
            const neuronObject = neuronData[0]; // Extract the neuron object

            console.log("Neuron object after loadNeuron():", neuronObject);

            // Add neuron object to the scene
            if (neuronObject && neuronObject.isObject3D) {
                s.scene.add(neuronObject);
                console.log("Neuron object successfully added to the scene.");
            } else {
                console.warn("Neuron object is missing or invalid.");
            }

            const neuron = s.scene.getObjectByName('neuron');

            if (neuron) {
                console.log("Neuron found! Proceeding with color update.");
                updateNodeAndEdgeColors(s, single_branch);
                adjustCameraForNeuron(s);
            } else {
                console.warn("Neuron still not found in the scene.");
            }

            console.log("Neuron object scale:", neuron.scale);
            console.log("Neuron object position:", neuron.position);
            console.log("Neuron object visibility:", neuron.visible);

            console.log("Neuron children count:", neuron.children.length);
            neuron.children.forEach(child => {
                console.log("Child Type:", child.type);
                console.log("Child Geometry:", child.geometry);
            });

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
 * Updates the colors of nodes and edges in the neuron visualization.
 *
 * @param {Object} viewer - The viewer object containing the scene.
 * @param {Array} neuron_section - An array of neuron section identifiers to be highlighted.
 * @param {string} [color1="#00FF00"] - The color to use for highlighting nodes and edges.
 * @param {string} [color2="#FF0000"] - The default color for nodes and edges.
 */
function updateNodeAndEdgeColors(viewer, neuron_section, color1 = "#00FF00", color2 = "#FF0000") {

    const neuron = viewer.scene.getObjectByName('neuron');
    if (!neuron) {
        console.error("Neuron object not found.");
        return;
    }

    console.log("Neuron found! Proceeding with coloring.");

    const highlightColor = new THREE.Color(color1);
    const defaultColor = new THREE.Color(color2);
    const neuronSet = new Set(neuron_section);

    const points = neuron.children.find(child => child.type === "Points");
    if (!points) {
        console.error("Points object not found.");
        return;
    }

    console.log("Before updating colors, Points geometry:", points.geometry.attributes);

    updateNodeColors(points, neuronSet, highlightColor, defaultColor);

    console.log("After updating colors, Points geometry:", points.geometry.attributes);

    const cones = neuron.children.find(child => child.type === "Mesh");
    if (!cones) {
        console.error("Cones object not found.");
        return;
    }

    console.log("Before updating colors, Cones geometry:", cones.geometry.attributes);

    updateEdgeColors(cones, neuronSet, highlightColor, defaultColor);

    console.log("After updating colors, Cones geometry:", cones.geometry.attributes);

    //viewer.setColor(neuron, highlightColor);
    //points.geometry.attributes.color.needsUpdate = true;

}


/**
 * Updates the colors of nodes in a 3D points geometry based on a set of highlighted neurons.
 *
 * @param {THREE.Points} points - The points geometry whose node colors will be updated.
 * @param {Set<number>} neuronSet - A set of node indices that should be highlighted.
 * @param {THREE.Color} highlightColor - The color to use for highlighted nodes.
 * @param {THREE.Color} defaultColor - The color to use for non-highlighted nodes.
 */
function updateNodeColors(points, neuronSet, highlightColor, defaultColor) {
    const numNodes = points.geometry.attributes.position.count; // Ensure buffer sizes match
    const colors = new Float32Array(numNodes * 3); // Each vertex needs an RGB triplet

    for (let i = 0; i < numNodes; i++) {
        if (neuronSet.has(i)) {
            colors.set([highlightColor.r, highlightColor.g, highlightColor.b], i * 3);
            if (points.material.uniforms && points.material.uniforms.grey_out) {
                points.material.uniforms.grey_out.value = 0;  // Enable color updates only for changed nodes
            }
        } else {
            colors.set([defaultColor.r, defaultColor.g, defaultColor.b], i * 3);
        }
    }

    points.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

    points.material.vertexColors = true;
    points.material.needsUpdate = true;
    points.geometry.attributes.color.needsUpdate = true;
}


/**
 * Updates the colors of edges in a 3D geometry based on a set of highlighted neurons.
 *
 * @param {THREE.Object3D} cones - The 3D object containing the geometry of the edges.
 * @param {Set<number>} neuronSet - A set of neuron indices to be highlighted.
 * @param {THREE.Color} highlightColor - The color to use for highlighted neurons.
 * @param {THREE.Color} defaultColor - The default color for non-highlighted neurons.
 */
function updateEdgeColors(cones, neuronSet, highlightColor, defaultColor) {
    const numEdges = cones.geometry.attributes.position.count;
    const colors = new Float32Array(numEdges * 3); // Must match position buffer

    for (let i = 0; i < numEdges; i++) {
        if (neuronSet.has(i)) {
            colors.set([highlightColor.r, highlightColor.g, highlightColor.b], i * 3);
            if (cones.material.uniforms && cones.material.uniforms.grey_out) {
                console.log("Setting grey_out value to 0.");
                cones.material.uniforms.grey_out.value = 0;  // Enable color updates only for changed edges
            }
        } else {
            colors.set([defaultColor.r, defaultColor.g, defaultColor.b], i * 3);
        }
    }

    cones.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

    cones.material.vertexColors = true;
    cones.material.needsUpdate = true;
    cones.geometry.attributes.color.needsUpdate = true;
}

function adjustCameraForNeuron(viewer) {

    const neuron = viewer.scene.getObjectByName('neuron');
    if (!neuron) {
        console.error("Neuron object not found in scene.");
        return;
    }

    // Calculate the bounding box of the neuron
    const boundingBox = new THREE.Box3().setFromObject(neuron);
    const size = boundingBox.getSize(new THREE.Vector3());
    const center = boundingBox.getCenter(new THREE.Vector3());

    console.log("Neuron Bounding Box Size:", size);
    console.log("Neuron Bounding Box Center:", center);

    // Compute the largest dimension of the neuron, the field of view, and the distance
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = viewer.camera.fov * (Math.PI / 180);
    const distance = (maxDim / 2) / Math.tan(fov / 2);

    // Adjust Camera Position to See the Whole Neuron
    viewer.camera.position.set(center.x, center.y, center.z + distance*0.8);
    viewer.camera.lookAt(center);

    // Adjust Clipping Planes to Avoid Clipping Issues
    viewer.camera.near = distance / 10; // Keep a small near clipping plane
    viewer.camera.far = distance * 10; // Ensure far objects remain visible
    viewer.camera.updateProjectionMatrix();

    console.log("Camera adjusted to fit neuron completely.");
}


/**
 * Adds ambient and directional lights to the given scene if they do not already exist.
 *
 * @param {THREE.Scene} scene - The scene to which the lights will be added.
 */
function addLights(scene) {
    let ambientName = "ambient-light";
    if (!scene.getObjectByName(ambientName)) {
      const ambientLight = new THREE.AmbientLight(Color.white, 1.0);
      ambientLight.name = ambientName;
      scene.add(ambientLight);
    }
    let directionalName = "directional-light";
    if (!scene.getObjectByName(directionalName)) {
      const directionalLight = new THREE.DirectionalLight(Color.grey, 0.4);
      directionalLight.name = directionalName;
      scene.add(directionalLight);
    }
  }
