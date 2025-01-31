
const single_branch = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 50, 51, 52, 58, 59, 60, 61, 62, 63, 64, 65, 66, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 98, 99, 100, 101, 102, 103, 104, 105, 110, 111, 112, 113, 114, 115, 116, 117, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 146, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 170, 171, 172, 173, 174, 175, 183, 184, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 211, 219, 220, 221, 222, 223, 224, 225, 226, 227, 231, 232, 233, 234, 235, 236, 244, 245, 246, 247, 248, 249, 250, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279];

window.onload = () => {
    document.getElementById("swc_input").addEventListener("change", readSwcFile, false);

    try {
        s = new sharkViewer.default({
            animated: false,
            mode: 'particle',
            dom_element: document.getElementById('container'),
            showAxes: 10000,
            showStats: true,
            maxVolumeSize: 5000000,
            cameraChangeCallback: () => console.log("Camera position updated")
        });

        window.s = s;
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
* This function reads the selected SWC file using a FileReader, parses it,
* and loads the neuron data into the viewer. If the file is invalid or an error occurs,
* appropriate alerts are shown to the user. After successfully loading the SWC data,
* it updates the node and edge colors in the viewer.
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
            let swc = sharkViewer.swcParser(swcTxt);

            if (swc && Object.keys(swc).length > 0) {

                s.swc = swc;
                s.loadNeuron('neuron', null, swc, true, false, true);
                console.log("SWC data loaded successfully.");

                // Update node and edge colors
                setTimeout(() => {
                    updateNodeAndEdgeColors(s, single_branch);
                    console.log("Node colors updated.");
                }, 1000);

                s.render();

            } else {
                alert("Invalid SWC file format.");
            }
        } catch (error) {
            console.error("Error parsing SWC file:", error);
            alert("An error occurred while processing the SWC file.");
        }
    };
    reader.readAsText(file);
}

/**
 * Updates the colors of nodes and edges in a neuron visualization.
 *
 * @param {Object} viewer - The viewer object containing the scene and rendering methods.
 * @param {Array<number>} neuron_section - An array of neuron node IDs to be highlighted.
 * @param {string} [color1="#00FF00"] - The color to use for highlighting nodes and edges (default is green).
 * @param {string} [color2="#FF0000"] - The default color for nodes and edges (default is red).
 */
function updateNodeAndEdgeColors(viewer, neuron_section, color1 = "#00FF00", color2 = "#FF0000") {
    const neuron = viewer.scene.getObjectByName('neuron');

    if (!neuron) {
        console.error("Neuron not found in the scene.");
        return;
    }

    // Convert color strings to THREE.Color objects
    const highlightColor = new THREE.Color(color1);
    const defaultColor = new THREE.Color(color2);

    const neuronSet = new Set(neuron_section);

    // Find the Points object containing the neuron nodes
    const points = neuron.children.find(child => child.type === "Points");
    if (!points) {
        console.error("Points object not found.");
        return;
    }

    const indexLookup = buildIndexToIDMapping(viewer.swc);

    points.userData.indexLookup = indexLookup;

    updateNodeColors(points, neuronSet, indexLookup, highlightColor, defaultColor);

    // Find the Cones object containing the neuron edges
    const cones = neuron.children.find(child => child.type === "Mesh");
    if (!cones) {
        console.error("Cones object not found.");
        return;
    }

    const vertexToNodeID = buildVertexToNodeIDMapping(cones.geometry, indexLookup);

    updateEdgeColors(cones, neuronSet, vertexToNodeID, highlightColor, defaultColor);

    console.log("Node and edge colors updated.");
}


/**
 * Builds a mapping from index to node ID for the given viewer's SWC data.
 *
 * @param {Object} swc - The SWC data object where keys are node IDs.
 * @returns {Object} An object where keys are indices and values are node IDs as integers.
 */
function buildIndexToIDMapping(swc) {
    const indexLookup = {};
    Object.keys(swc).forEach((nodeId, i) => {
        indexLookup[i] = parseInt(nodeId);
    });
    return indexLookup;
}

/**
 * Builds a mapping from vertex positions to node IDs.
 *
 * @param {THREE.BufferGeometry} geometry - The geometry object containing positions.
 * @param {Object} indexLookup - A lookup table mapping vertex indices to node IDs.
 * @returns {Object} A mapping where keys are position strings and values are node IDs.
 */
function buildVertexToNodeIDMapping(geometry, indexLookup) {
    const vertexToNodeID = {};
    const positions = geometry.attributes.position.array;

    Object.keys(indexLookup).forEach(key => {
        const nodeID = indexLookup[key];
        const vertexIndex = parseInt(key);
        const posString = getPositionString(vertexIndex, positions);
        vertexToNodeID[posString] = nodeID;
    });

    return vertexToNodeID;
}

/**
 * Updates the colors of nodes in a 3D points geometry based on a set of neuron IDs.
 *
 * @param {THREE.Points} points - The 3D points geometry whose node colors will be updated.
 * @param {Set<number>} neuronSet - A set of neuron IDs that should be highlighted.
 * @param {Object} indexLookup - An object mapping node indices to neuron IDs.
 * @param {THREE.Color} highlightColor - The color to use for highlighted neurons.
 * @param {THREE.Color} defaultColor - The color to use for non-highlighted neurons.
 */
function updateNodeColors(points, neuronSet, indexLookup, highlightColor, defaultColor) {
    const numNodes = points.geometry.attributes.position.count;
    const newColors = new Float32Array(numNodes * 3);

    for (let i = 0; i < numNodes; i++) {
        const nodeID = indexLookup[i];
        const color = neuronSet.has(nodeID) ? highlightColor : defaultColor;
        newColors.set([color.r, color.g, color.b], i * 3);
    }

    points.geometry.setAttribute("typeColor", new THREE.Float32BufferAttribute(newColors, 3));
    points.geometry.attributes.typeColor.needsUpdate = true;
}

/**
 * Updates the edge colors of a given geometry based on the provided neuron set.
 *
 * @param {THREE.BufferGeometry} cones - The geometry object containing the edges to be colored.
 * @param {Set<number>} neuronSet - A set of neuron IDs to be highlighted.
 * @param {Object} vertexToNodeID - A lookup table mapping vertex positions to node IDs.
 * @param {THREE.Color} highlightColor - The color to use for highlighted edges.
 * @param {THREE.Color} defaultColor - The default color to use for non-highlighted edges.
 */
function updateEdgeColors(cones, neuronSet, vertexToNodeID, highlightColor, defaultColor) {
    const indices = cones.geometry.index.array;
    const positions = cones.geometry.attributes.position.array;
    const numFaces = indices.length / 3;
    const edgeColors = new Float32Array(positions.length);

    console.log("Num indices: ", indices);
    console.log("Num positions: ", positions.length);
    console.log("Num faces: ", numFaces);

    // Initialize edgeColors with the default color
    for (let i = 0; i < positions.length / 3; i++) {
        edgeColors.set([defaultColor.r, defaultColor.g, defaultColor.b], i * 3);
    }

    for (let i = 0; i < numFaces; i++) {
        // Get the three vertex positions for the current face
        const [v1, v2, v3] = [indices[i * 3], indices[i * 3 + 1], indices[i * 3 + 2]];

        // Get the node IDs for the three vertices
        const [pos1, pos2, pos3] = [getPositionString(v1, positions), getPositionString(v2, positions), getPositionString(v3, positions)];

        // Get the node IDs for the three vertices
        const [nodeID1, nodeID2, nodeID3] = [vertexToNodeID[pos1], vertexToNodeID[pos2], vertexToNodeID[pos3]];

        const isHighlighted = nodeID1 && neuronSet.has(nodeID1) || nodeID2 && neuronSet.has(nodeID2) || nodeID3 && neuronSet.has(nodeID3);

        if (isHighlighted) {
            edgeColors.set([highlightColor.r, highlightColor.g, highlightColor.b], v1 * 3);
            edgeColors.set([highlightColor.r, highlightColor.g, highlightColor.b], v2 * 3);
            edgeColors.set([highlightColor.r, highlightColor.g, highlightColor.b], v3 * 3);
        }
    }

    cones.geometry.setAttribute("typeColor", new THREE.Float32BufferAttribute(edgeColors, 3));
    cones.geometry.attributes.typeColor.needsUpdate = true;
}

/**
 * Generates a position string from an array of positions.
 *
 * @param {number} index - The index of the position to retrieve.
 * @param {Array<number>} positions - The array containing position values.
 * @returns {string} A string representing the position in the format "x,y,z".
 */
function getPositionString(index, positions) {
    return `${positions[index * 3].toFixed(4)},${positions[index * 3 + 1].toFixed(4)},${positions[index * 3 + 2].toFixed(4)}`;
}
