import SharkViewer, { swcParser, Color, NODE_PARTICLE_IMAGE } from "./SharkViewer/shark_viewer.js";
import SynapseShader from "./shaders/SynapseShader.js";

window.onload = async () => {
    window.maxVolumeSize = 1000000;

    const neuronReady = $("script[src*='viewer.js']").data("neuron-ready") === true;
    const initialLoad = $("script[src*='viewer.js']").data("initial-load") === true;
    const sectionArrays = $("script[src*='viewer.js']").data("neuron-sections");
    const synapsePointCloud = $("script[src*='viewer.js']").data("synapse-point-cloud");

    let activeNeuronSection = parseInt($("script[src*='viewer.js']").data("active-neuron-section"));
    activeNeuronSection = isNaN(activeNeuronSection) ? -1 : activeNeuronSection;

    let activeSynapseIDs = $("script[src*='viewer.js']").data("active-synapse-ids");

    // Ensure it's an array
    if (!Array.isArray(activeSynapseIDs)) {
        try {
            activeSynapseIDs = JSON.parse(activeSynapseIDs || "[]");
        } catch (e) {
            console.error("Error parsing active-synapse-ids:", e);
            activeSynapseIDs = [];
        }
    }

    const $sharkContainerMinimap = $("#shark_container_minimap");

    window.sectionColors = generateSectionColors(sectionArrays);

    if (neuronReady) {
        if (initialLoad) {
            window.synapseColors = {};
            sessionStorage.removeItem("synapseColors");
        }

        try {
            await initializeViewer($sharkContainerMinimap[0], maxVolumeSize, sectionArrays, activeNeuronSection);

            const swcTxt = await loadSwcFile();
            processSwcFile(swcTxt, sectionArrays, activeNeuronSection, activeSynapseIDs);

            if (synapsePointCloud) {
                updateLoadingBar(parseInt(synapsePointCloud.length / 3), activeSynapseIDs);
                processSynapseCloudData(synapsePointCloud, maxVolumeSize, activeSynapseIDs, initialLoad);
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
};

async function initializeViewer(sharkContainerMinimap, maxVolumeSize, sectionArrays, activeNeuronSection) {
    const sectionMetadata = generateSectionMetadata(sectionArrays);

    window.window.shark = new SharkViewer({
        mode: 'particle',
        dom_element: sharkContainerMinimap,
        maxVolumeSize: maxVolumeSize,
        metadata: sectionMetadata,
        colors: window.sectionColors,
    });

    console.log("Viewer initialized with section-based metadata.");
    await window.shark.init();
    window.shark.animate();

    const mElement = createMetadataElement(sectionMetadata, window.sectionColors, activeNeuronSection);
    const oldElement = document.getElementById("node_key");
    if (oldElement) {
        oldElement.remove();
    }
    sharkContainerMinimap.appendChild(mElement);
}

window.setupWindowResizeHandler = (sharkContainerMinimap) => {
    $(window).on('resize', () => onWindowResize(sharkContainerMinimap));
    setTimeout(() => {
        onWindowResize(sharkContainerMinimap);
        window.window.shark.render();
    }, 100);
};

async function loadSwcFile() {
    try {
        const response = await fetch(`/get_swc`);

        if (!response.ok) {
            console.error("Failed to fetch SWC file.");
            return;
        }

        const swcText = await response.text();
        return swcText;
    } catch (error) {
        console.error("Error fetching SWC file:", error);
        alert("An error occurred while fetching the SWC file.");
        throw error;
    }
}

function processSwcFile(swcTxt, sectionArrays, activeNeuronSection, activeSynapseIDs) {
    const swc = swcParser(swcTxt);

    if (!swc || Object.keys(swc).length === 0) {
        console.error("SWC parsing failed. The SWC object is empty.");
        return;
    }

    window.window.shark.swc = swc;

    const neuronData = window.shark.loadNeuron('neuron', 'red', swc, sectionArrays, true, false, true);
    const neuronObject = neuronData[0];

    if (neuronObject && neuronObject.isObject3D) {
        window.shark.scene.add(neuronObject);
        console.log("Neuron object successfully added to the scene.");
    } else {
        console.warn("Neuron object is missing or invalid.");
    }

    const neuron = window.shark.scene.getObjectByName('neuron');

    if (neuron) {
        console.log("Neuron found! Proceeding with color update.");
        updateNodeAndEdgeColors(window.shark, sectionArrays, activeNeuronSection);
        setTimeout(() => adjustCameraForNeuron(window.shark, sectionArrays, activeNeuronSection, activeSynapseIDs), 500);
    } else {
        console.warn("Neuron still not found in the scene.");
    }

    addLights(window.shark.scene);
    window.shark.render();
}

function processSynapseCloudData(data, maxVolumeSize, activeSynapseIDs, initialLoad) {
    if (!Array.isArray(data) || data.length % 3 !== 0) {
        console.error("JSON data is not an Array or length is not a multiple of 3.");
        return;
    }

    window.synapseColors = JSON.parse(sessionStorage.getItem("synapseColors")) || {};

    const points = [];
    for (let i = 0; i < data.length; i += 3) {
        points.push(new THREE.Vector3(data[i], data[i + 1], data[i + 2]));
    }

    const positions = new Float32Array(points.length * 3);
    const colors = new Float32Array(points.length * 4);
    const alphas = new Float32Array(points.length);
    const sizes = new Float32Array(points.length);

    for (let i = 0; i < points.length; i++) {
        positions[i * 3] = points[i].x + Math.random() * 800;
        positions[i * 3 + 1] = points[i].y + Math.random() * 800;
        positions[i * 3 + 2] = points[i].z + Math.random() * 800;

        if (!window.synapseColors[i]) {
            window.synapseColors[i] = "yellow";
        }

        const colorHex = window.synapseColors[i] === "green" ? 0x00ff00 :
                         window.synapseColors[i] === "red" ? 0xff0000 : 0xffff00;

        const color = new THREE.Color(colorHex);
        colors[i * 4] = color.r;
        colors[i * 4 + 1] = color.g;
        colors[i * 4 + 2] = color.b;
        colors[i * 4 + 3] = 1.0;

        if (activeSynapseIDs.length > 0) {
            sizes[i] = activeSynapseIDs.includes(i) ? maxVolumeSize : 5;
            alphas[i] = window.synapseColors[i] === "green" || window.synapseColors[i] === "red" || activeSynapseIDs.includes(i) ? 1.0 : 0.2;

            window.synapseColors[i] === "green" || window.synapseColors[i] === "red" ? 1.0 : 0.2;

        } else if (initialLoad) {
            sizes[i] = 10;
            alphas[i] = 1.0;
        } else {
            sizes[i] = 10;
            alphas[i] = 0.4;
        }
    }

    sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 4));
    geometry.setAttribute("radius", new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute("alpha", new THREE.BufferAttribute(alphas, 1));

    const image = document.createElement("img");
    const sphereTexture = new THREE.Texture(image);
    image.onload = () => {
        sphereTexture.needsUpdate = true;
    };
    image.src = NODE_PARTICLE_IMAGE;

    SynapseShader.uniforms["sphereTexture"].value = sphereTexture;

    const material = new THREE.ShaderMaterial({
        uniforms: SynapseShader.uniforms,
        vertexShader: SynapseShader.vertexShader,
        fragmentShader: SynapseShader.fragmentShader,
        vertexColors: true,
        transparent: true,
        depthTest: true,     // Objects still get depth-culled
        depthWrite: false,   // Prevents particles from overwriting depth buffer
        renderOrder: 2
    });

    const pointsMesh = new THREE.Points(geometry, material);
    pointsMesh.name = "synapse-cloud";

    window.shark.scene.add(pointsMesh);
    window.shark.scene.needsUpdate = true;

    window.shark.render();
    console.log("Synapse cloud successfully added.");
}

function updateNodeAndEdgeColors(viewer, sectionArrays, activeNeuronSection) {
    const neuron = viewer.scene.getObjectByName("neuron");
    if (!neuron) {
        console.error("Neuron object not found.");
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
    if (activeNeuronSection >= 0) {
        console.log("Some sections get greyed out");
        vertexGreyOut = new Float32Array(numVertices).fill(1.0);
        edgeGreyOut = new Float32Array(numVertices * 6).fill(1.0);
    } else {
        console.log("No part gets greyed out");
        vertexGreyOut = new Float32Array(numVertices).fill(0.0);
        edgeGreyOut = new Float32Array(numVertices * 6).fill(0.0);
    }

    sectionArrays.forEach((nodeGroup, index) => {
        const color = new THREE.Color(window.sectionColors[index] || 0xffffff);

        nodeGroup.forEach(nodeIndex => {
            if (nodeIndex < numVertices) {
                vertexColors.set([color.r, color.g, color.b], nodeIndex * 3);
            }

            if (nodeIndex < numEdges) {
                edgeColors.set([color.r, color.g, color.b], (nodeIndex - 1) * 6 * 3);
                edgeColors.set([color.r, color.g, color.b], (nodeIndex - 1) * 6 * 3 + 3);
                edgeColors.set([color.r, color.g, color.b], (nodeIndex - 1) * 6 * 3 + 6);
                edgeColors.set([color.r, color.g, color.b], (nodeIndex - 1) * 6 * 3 + 9);
                edgeColors.set([color.r, color.g, color.b], (nodeIndex - 1) * 6 * 3 + 12);
                edgeColors.set([color.r, color.g, color.b], (nodeIndex - 1) * 6 * 3 + 15);
            }

            if (activeNeuronSection === index) {
                vertexGreyOut[(nodeIndex - 1)] = 0.0;
                edgeGreyOut[(nodeIndex - 1) * 6] = 0.0;
                edgeGreyOut[(nodeIndex - 1) * 6 + 1] = 0.0;
                edgeGreyOut[(nodeIndex - 1) * 6 + 2] = 0.0;
                edgeGreyOut[(nodeIndex - 1) * 6 + 3] = 0.0;
                edgeGreyOut[(nodeIndex - 1) * 6 + 4] = 0.0;
                edgeGreyOut[(nodeIndex - 1) * 6 + 5] = 0.0;
            }
        });
    });

    skeletonVertex.geometry.setAttribute("color", new THREE.Float32BufferAttribute(vertexColors, 3));
    skeletonEdge.geometry.setAttribute("color", new THREE.Float32BufferAttribute(edgeColors, 3));

    skeletonVertex.geometry.attributes.color.needsUpdate = true;
    skeletonEdge.geometry.attributes.color.needsUpdate = true;

    skeletonVertex.geometry.setAttribute("grey_out", new THREE.Float32BufferAttribute(vertexGreyOut, 1));
    skeletonEdge.geometry.setAttribute("grey_out", new THREE.Float32BufferAttribute(edgeGreyOut, 1));

    skeletonVertex.geometry.attributes.color.needsUpdate = true;
    skeletonEdge.geometry.attributes.color.needsUpdate = true;

    console.log("Node and edge colors applied successfully.");

    viewer.render();
}

window.greyOutSectionsAlpha = (viewer, sectionArrays, greyOutSections) => {
    const neuron = viewer.scene.getObjectByName("neuron");
    if (!neuron) {
        console.error("Neuron object not found.");
        return;
    }

    const skeletonVertex = neuron.children.find(child => child.name === "skeleton-vertex");
    const skeletonEdge = neuron.children.find(child => child.name === "skeleton-edge");

    if (!skeletonVertex || !skeletonEdge) {
        console.error("Skeleton vertex or edge objects not found.");
        return;
    }

    const numVertices = skeletonVertex.geometry.attributes.position.count;
    const numEdges = skeletonEdge.geometry.attributes.position.count;

    const vertexGreyOut = new Float32Array(numVertices).fill(0.0);
    const edgeGreyOut = new Float32Array(numVertices * 6).fill(0.0);

    greyOutSections.forEach(sectionIndex => {
        sectionArrays[sectionIndex].forEach(vertexIndex => {
            vertexGreyOut[vertexIndex - 1] = 1.0;

            edgeGreyOut[(vertexIndex - 1) * 6] = 1.0;
            edgeGreyOut[(vertexIndex - 1) * 6 + 1] = 1.0;
            edgeGreyOut[(vertexIndex - 1) * 6 + 2] = 1.0;
            edgeGreyOut[(vertexIndex - 1) * 6 + 3] = 1.0;
            edgeGreyOut[(vertexIndex - 1) * 6 + 4] = 1.0;
            edgeGreyOut[(vertexIndex - 1) * 6 + 5] = 1.0;
        });
    });

    skeletonVertex.geometry.setAttribute("grey_out", new THREE.Float32BufferAttribute(vertexGreyOut, 1));
    skeletonEdge.geometry.setAttribute("grey_out", new THREE.Float32BufferAttribute(edgeGreyOut, 1));

    skeletonVertex.geometry.attributes.color.needsUpdate = true;
    skeletonEdge.geometry.attributes.color.needsUpdate = true;

    viewer.render();
};

window.updateSynapse = (index, newPosition = null, newColor = null, newSize = null, save_in_session = true) => {
    const pointsMesh = window.shark.scene.getObjectByName("synapse-cloud");
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

    if (newPosition) {
        positions.setXYZ(index, newPosition.x, newPosition.y, newPosition.z);
        positions.needsUpdate = true;
    }

    if (newColor) {
        colors.setXYZ(index, newColor.r, newColor.g, newColor.b);
        colors.needsUpdate = true;

        const colorLabel = newColor.getHex() === 0x00ff00 ? "green" :
                           newColor.getHex() === 0xff0000 ? "red" : "yellow";

        window.synapseColors[index] = colorLabel;

        if (save_in_session) {
            sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));
        }
    }

    if (newSize !== null) {
        sizes.setX(index, newSize);
        sizes.needsUpdate = true;
    }

    window.shark.render();
};

function adjustCameraForNeuron(viewer, sectionArrays, activeNeuronSection, activeSynapseIDs) {
    if (!viewer || !viewer.camera || !viewer.scene) {
        console.error("Viewer or camera not initialized yet.");
        return;
    }

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

    distance = Math.max(50, Math.min(distance, 1000000)); // Keep within reasonable bounds

    console.log("Adjusting camera. Distance:", distance, "Bounding box size:", size);

    let targetPosition = center;

    if (activeSynapseIDs.length > 0) {
        const firstSynapseIndex = activeSynapseIDs[0];
        const pointsMesh = viewer.scene.getObjectByName("synapse-cloud");
        if (pointsMesh) {
            const positions = pointsMesh.geometry.getAttribute("position");
            targetPosition = new THREE.Vector3(
                positions.getX(firstSynapseIndex),
                positions.getY(firstSynapseIndex),
                positions.getZ(firstSynapseIndex)
            );
        }
    } else if (activeNeuronSection >= 0) {
        const sectionNodes = sectionArrays[activeNeuronSection];
        if (sectionNodes && sectionNodes.length > 0) {
            const firstNodeIndex = sectionNodes[0];
            const skeletonVertex = neuron.children.find(child => child.name === "skeleton-vertex");
            if (skeletonVertex && skeletonVertex.geometry) {
                const positions = skeletonVertex.geometry.getAttribute("position");
                targetPosition = new THREE.Vector3(
                    positions.getX(firstNodeIndex),
                    positions.getY(firstNodeIndex),
                    positions.getZ(firstNodeIndex)
                );
            } else {
                console.error("skeleton-vertex or its geometry not found.");
            }
        }
    }

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
    viewer.camera.far = distance * 2;
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

function generateSectionColors(sectionArrays) {
    const colors = [];
    const numSections = sectionArrays.length;

    for (let i = 0; i < numSections; i++) {
        const hue = (i / numSections) * 1.0; // Spread colors evenly
        colors.push(new THREE.Color().setHSL(hue, 1.0, 0.4));
    }
    return colors;
}

function generateSectionMetadata(sectionArrays) {
    return sectionArrays.map((_, index) => ({
        "label": `Sec. ${index + 1}`, // Assign a readable name
        "type": index  // Unique type ID for this section
    }));
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

function createMetadataElement(metadata, colors, activeNeuronSection) {
    const metadiv = document.createElement("div");
    metadiv.id = "node_key";
    metadiv.style.position = "absolute";
    metadiv.style.top = "60px";
    metadiv.style.right = "10px";
    metadiv.style.background = "white";
    metadiv.style.border = "solid 1px #aaaaaa";
    metadiv.style.borderRadius = "5px";
    metadiv.style.padding = "5px";
    metadiv.style.fontFamily = "Arial, sans-serif";
    metadiv.style.fontSize = "12px";
    metadiv.style.maxWidth = "150px";
    metadiv.style.maxHeight = "calc(75%)";
    metadiv.style.overflowY = "auto";
    metadiv.style.zIndex = "1000";
    metadiv.style.pointerEvents = "auto";

    let toinnerhtml = "<strong>Sections</strong><br>";
    metadata.forEach((m, index) => {
        let cssColor = colors[index] instanceof THREE.Color
            ? `rgb(${colors[index].r * 255}, ${colors[index].g * 255}, ${colors[index].b * 255})`
            : convertToHexColor(colors[index]);

        let isActive = activeNeuronSection === index;
        let activeStyle = isActive ? "font-weight: bold; background: rgba(229, 218, 6, 0.41);" : "";
        let hoverStyle = "onmouseover=\"if (!this.classList.contains('active-section')) this.style.background='rgba(200, 200, 200, 0.5)';\""
                       + " onmouseout=\"if (!this.classList.contains('active-section')) this.style.background='';\"";

        toinnerhtml += `<div class='section-entry ${isActive ? "active-section" : ""}'
                            data-section-index="${index}"
                            style='padding: 3px; cursor: pointer; ${activeStyle}'
                            ${hoverStyle}>
            <span style='display: inline-block; width: 12px; height: 12px; background: ${cssColor}; margin-right: 5px; border-radius: 4px; position: relative; top: 2px;'></span>
            ${m.label}
        </div>`;
    });

    metadiv.innerHTML = toinnerhtml;

    // Click event for each section entry
    metadiv.querySelectorAll(".section-entry").forEach(entry => {
        entry.addEventListener("click", function () {
            const sectionIndex = this.getAttribute("data-section-index");

            // 🔹 First, check if retrieve_instance_metadata is locked
            fetch("/is_metadata_locked")
                .then(response => response.json())
                .then(data => {
                    if (data.locked) {
                        alert("Data update is currently in progress. Please wait before navigating.");
                    } else {
                        // Proceed only if the lock is free
                        fetch(`/retrieve_first_page_of_section/${sectionIndex}`)
                .then(response => response.json())
                .then(data => {
                    if (data.page) {
                        window.location.href = `/annotation/${data.page}`;
                    } else {
                        alert("Failed to retrieve section page.");
                    }
                })
                .catch(error => console.error("Error fetching first page:", error));
                    }
                })
                .catch(error => console.error("Error checking metadata lock:", error));
        });
    });

    metadiv.addEventListener("wheel", (e) => {
        e.stopPropagation();
    });

    const minimapContainer = document.getElementById("shark_container_minimap");
    minimapContainer.appendChild(metadiv);

    return metadiv;
}


function updateLoadingBar(synapse_count, activeSynapseIDs) {
    if (!Array.isArray(activeSynapseIDs)) {
        console.error("activeSynapseIDs is not an array!", activeSynapseIDs);
        activeSynapseIDs = [];
    }

    if (activeSynapseIDs.length === 0) return;

    const lowestDisplayedSectionIdx = Math.min(...activeSynapseIDs);
    const progressPercent = (lowestDisplayedSectionIdx / synapse_count) * 100;

    document.getElementById("loading_progress").style.width = `${progressPercent}%`;
}
