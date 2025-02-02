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

function updateNodeAndEdgeColors(viewer, neuron_section, color1 = Color.blue, color2 = Color.red) {
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
        console

        skeletonVertex.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        skeletonVertex.geometry.attributes.color.needsUpdate = true;
        skeletonVertex.material.vertexColors = true;
        skeletonVertex.material.needsUpdate = true;

        console.log("Node colors applied successfully.");
    } else {
        console.warn("skeleton-vertex not found or has no geometry.");
    }

    // Update edge colors (skeleton-edge)
    if (skeletonEdge && skeletonEdge.geometry && skeletonEdge.geometry.attributes.position) {
        console.log("Updating edge colors...");
        const numEdges = skeletonEdge.geometry.attributes.position.count;
        const colors = new Float32Array(numEdges * 3);

        console.log("Number of edges:", numEdges);
        for (let i = 0; i < numEdges; i++) {
            const isHighlighted = edges.has(i);
            const color = isHighlighted ? new THREE.Color(color1) : new THREE.Color(color2);
            colors.set([color.r, color.g, color.b], i * 3);
        }

        // Assign per-edge colors
        skeletonEdge.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        skeletonEdge.geometry.attributes.color.needsUpdate = true;
        skeletonEdge.material.vertexColors = true;
        skeletonEdge.material.needsUpdate = true;

        console.log("Edge colors applied successfully.");
    } else {
        console.warn("skeleton-edge not found or has no geometry.");
    }

    // Ensure visibility of both components
    if (skeletonVertex) skeletonVertex.visible = true;
    if (skeletonEdge) skeletonEdge.visible = true;

    viewer.render();
}


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
