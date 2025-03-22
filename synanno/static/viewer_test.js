import SharkViewer, { swcParser, Color } from "./SharkViewer/shark_viewer.js";

let sectionArrays = [];
const distinct_neuron = "neuron_3955003482_scaled.swc";

window.onload = async () => {
    window.maxVolumeSize = 1000000;

    const $swcInput = $("#swc_input");

    const $sharkContainerMinimap = $("#shark_container_minimap");

    $swcInput.on("change", async (event) => {
        const files = event.target.files;
        if (files && files.length > 0) {
            try {
                // Ensure SharkViewer is initialized before processing the SWC files
                if (!window.window.shark) {
                    console.error("SharkViewer is not initialized. Initializing now...");
                    await initializeViewer(
                        $sharkContainerMinimap[0]
                    );
                }

                for (const file of files) {
                    const swcTxt = await file.text();
                    const swc = swcParser(swcTxt);

                    if (!swc || Object.keys(swc).length === 0) {
                        console.error(`SWC parsing failed for file ${file.name}. The SWC object is empty.`);
                        continue;
                    }

                    console.log(`SWC file ${file.name} loaded successfully.`);
                    window.window.shark.swc = swc;

                    // Call processSwcFile to render the neuron
                    processSwcFile(swcTxt, file.name);

                    adjustCameraForNeuron(
                        window.shark,
                        distinct_neuron
                    );
                    addLights(window.shark.scene);
                    window.shark.render();
                }

            } catch (error) {
                console.error("Error reading SWC files:", error);
            }
        }
    });

};

async function initializeViewer(sharkContainerMinimap) {

    window.window.shark = new SharkViewer({
        mode: 'particle',
        dom_element: sharkContainerMinimap,
        maxVolumeSize: maxVolumeSize,
        colors: window.sectionColors,
    });

    console.log("Viewer initialized with section-based metadata.");
    await window.shark.init();
    window.shark.animate();

}

window.setupWindowResizeHandler = (sharkContainerMinimap) => {
    $(window).on('resize', () => onWindowResize(sharkContainerMinimap));
    setTimeout(() => {
        onWindowResize(sharkContainerMinimap);
        window.window.shark.render();
    }, 100);
};

function processSwcFile(swcTxt, fileName) {
    const swc = swcParser(swcTxt);

    if (!swc || Object.keys(swc).length === 0) {
        console.error("SWC parsing failed. The SWC object is empty.");
        return;
    }

    window.window.shark.swc = swc;

    // Generate a unique name for the neuron
    const neuronName = `${fileName}`;

    const neuronData = window.shark.loadNeuron(
        neuronName,
        'red',
        swc,
        sectionArrays,
        true,
        false,
        true
    );
    const neuronObject = neuronData[0];

    if (neuronObject && neuronObject.isObject3D) {
        neuronObject.name = neuronName; // Assign the unique name
        console.log("neuronObject: ", neuronName);
        window.shark.scene.add(neuronObject);
        console.log(`Neuron object '${neuronName}' successfully added to the scene.`);
    } else {
        console.warn("Neuron object is missing or invalid.");
    }

    updateNodeAndEdgeColors(window.shark, neuronName, false); // neuronName !==distinct_neuron);

    // add little time out
}

function updateNodeAndEdgeColors(viewer, neuronName, grey_out = false) {
    const neuron = viewer.scene.getObjectByName(neuronName);
    if (!neuron) {
        console.error(`Neuron object '${neuronName}' not found.`);
        return;
    }

    const skeletonVertex = neuron.children.find(child => child.name === "skeleton-vertex");
    const skeletonEdge = neuron.children.find(child => child.name === "skeleton-edge");

    if (!skeletonVertex || !skeletonVertex.geometry || !skeletonEdge || !skeletonEdge.geometry) {
        console.warn("skeleton-vertex or skeleton-edge not found or missing geometry.");
        return;
    }

    const numVertices = skeletonVertex.geometry.attributes.position.count;
    const itemSizeVertices = skeletonVertex.geometry.attributes.position.itemSize;

    const numEdges = skeletonEdge.geometry.attributes.position.count;
    const itemSizeEdges = skeletonEdge.geometry.attributes.position.itemSize;

    const vertexColors = new Float32Array(numVertices * itemSizeVertices);
    const edgeColors = new Float32Array(numVertices * 6 * itemSizeEdges);

    let vertexGreyOut = [];
    let edgeGreyOut = [];

    if (grey_out) {
        vertexGreyOut = new Float32Array(numVertices).fill(1.0); // More translucent for greyed-out neurons
        edgeGreyOut = new Float32Array(numVertices * 6).fill(1.0); // More translucent for edges
    } else {
        vertexGreyOut = new Float32Array(numVertices).fill(0.0);
        edgeGreyOut = new Float32Array(numVertices * 6).fill(0.0);
    }

    // Random hue color for active neurons
    let color = new THREE.Color();
    if (grey_out){
        color.setHSL(0, 1.0, 1.0);
    } else{
        if (neuronName === distinct_neuron) {
            color.setHSL(0.0, 1.0, 0.5);
        }
        else{
            color.setHSL(Math.random(), 1.0, 0.5);
        }
    }

    // If sectionArrays is empty, color all nodes with the same color
    if (sectionArrays.length === 0) {
        for (let i = 0; i < numVertices; i++) {
            vertexColors.set([color.r, color.g, color.b], i * 3);
        }

        for (let i = 0; i < numEdges; i++) {
            if (i * 6 * 3 + 15 < edgeColors.length) {
                edgeColors.set([color.r, color.g, color.b], i * 6 * 3);
                edgeColors.set([color.r, color.g, color.b], i * 6 * 3 + 3);
                edgeColors.set([color.r, color.g, color.b], i * 6 * 3 + 6);
                edgeColors.set([color.r, color.g, color.b], i * 6 * 3 + 9);
                edgeColors.set([color.r, color.g, color.b], i * 6 * 3 + 12);
                edgeColors.set([color.r, color.g, color.b], i * 6 * 3 + 15);
            }
        }
    }

    skeletonVertex.geometry.setAttribute("color", new THREE.Float32BufferAttribute(vertexColors, 3));
    skeletonEdge.geometry.setAttribute("color", new THREE.Float32BufferAttribute(edgeColors, 3));

    skeletonVertex.geometry.attributes.color.needsUpdate = true;
    skeletonEdge.geometry.attributes.color.needsUpdate = true;

    skeletonVertex.geometry.setAttribute("grey_out", new THREE.Float32BufferAttribute(vertexGreyOut, 1));
    skeletonEdge.geometry.setAttribute("grey_out", new THREE.Float32BufferAttribute(edgeGreyOut, 1));

    console.log(`Node and edge colors applied successfully for '${neuronName}'.`);

    viewer.render();
}

function adjustCameraForNeuron(viewer, neuronName) {
    if (!viewer || !viewer.camera || !viewer.scene) {
        console.error("Viewer or camera not initialized yet.");
        return;
    }

    const neuron = viewer.scene.getObjectByName(neuronName);
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

    distance = Math.max(50, Math.min(distance, 1000000)); // Keep within reasonable bounds

    console.log("Adjusting camera. Distance:", distance, "Bounding box size:", size);

    let targetPosition = center;

    // Set camera position
    viewer.camera.position.set(targetPosition.x, targetPosition.y, targetPosition.z + distance * 0.5);
    viewer.camera.lookAt(targetPosition);

    // Ensure trackControls (OrbitUnlimitedControls) is used correctly
    if (viewer.trackControls) {
        viewer.trackControls.target.set(targetPosition.x, targetPosition.y, targetPosition.z);
        viewer.trackControls.update();
    } else {
        console.warn("Viewer trackControls not initialized yet. Retrying in 500ms...");
        setTimeout(() => {
            if (viewer.trackControls) {
                viewer.trackControls.target.set(targetPosition.x, targetPosition.y, targetPosition.z);
                viewer.trackControls.update();
            } else {
                console.error("Viewer trackControls still not available.");
            }
        }, 500);
    }

    // Adjust camera properties
    viewer.camera.near = 1;
    viewer.camera.far = distance * 20;
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

window.onWindowResize = function(sharkContainerMinimap) {
    if (!window.window.shark || !window.window.shark.camera) {
        console.error("SharkViewer not initialized yet. Skipping resize.");
        return;
    }

    if (!sharkContainerMinimap) {
        console.error("window.shark container not found.");
        return;
    }

    const width = sharkContainerMinimap.clientWidth || window.innerWidth;
    const height = sharkContainerMinimap.clientHeight || window.innerHeight;
    console.log("Resizing viewer to:", width, "x", height);

    if (width > 0 && height > 0) {
        window.window.shark.camera.aspect = width / height;
        window.window.shark.camera.updateProjectionMatrix();
        window.window.shark.renderer.setSize(width, height);
        window.window.shark.renderer.setPixelRatio(window.devicePixelRatio); // Improves scaling on high-res screens
    }

    window.window.shark.render();
}
