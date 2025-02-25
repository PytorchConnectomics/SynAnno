import SharkViewer, { swcParser, Color, NODE_PARTICLE_IMAGE } from "./SharkViewer/shark_viewer.js";
import SynapseShader from "./shaders/SynapseShader.js";

$(document).ready(() => {
    window.maxVolumeSize = 1000000;

    const neuronReady = $("script[src*='viewer.js']").data("neuron-ready") === true;
    const initialLoad = $("script[src*='viewer.js']").data("initial-load") === true;
    const neuronPath = $("script[src*='viewer.js']").data("neuron-path");
    const sectionArray = $("script[src*='viewer.js']").data("neuron-section");
    const synapseCloudPath = $("script[src*='viewer.js']").data("synapse-cloud-path");

    const $sharkContainerMinimap = $("#shark_container_minimap");

    window.sectionColors = generateSectionColors(sectionArray);

    if (neuronReady) {
        if (initialLoad) {
            window.synapseColors = {};
            sessionStorage.removeItem("synapseColors");
            console.log("Initial load, synapseColors cleared.");
        }

        console.log("Neuron data is ready. Initializing viewer...");
        try {
            initializeViewer($sharkContainerMinimap[0], maxVolumeSize, sectionArray);

            if (neuronPath) {
                loadSwcFile(neuronPath, sectionArray);
            } else {
                console.error("No neuron path provided.");
            }

            if (synapseCloudPath) {
                loadSynapseCloud(synapseCloudPath, maxVolumeSize);
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
function initializeViewer(sharkContainerMinimap, maxVolumeSize, sectionArray) {
    const sectionMetadata = generateSectionMetadata(sectionArray);

    window.s = new SharkViewer({
        mode: 'particle',
        dom_element: sharkContainerMinimap,
        maxVolumeSize: maxVolumeSize,
        metadata: sectionMetadata,
        colors: window.sectionColors,
    });

    console.log("Viewer initialized with section-based metadata.");
    s.init();
    s.animate();

    let collectSectionIndices = [];
    let sectionIdx = -1;
    $(".image-card-btn").each(function () {
        sectionIdx = parseInt($(this).attr("sectionIdx"))
        if (!collectSectionIndices.includes(sectionIdx)) {
            collectSectionIndices.push(sectionIdx);
        }
    });

    console.log("Collect section indices:", collectSectionIndices);

    const mElement = createMetadataElement(sectionMetadata, window.sectionColors, collectSectionIndices);
    const oldElement = document.getElementById("node_key");
    if (oldElement) {
        oldElement.remove();
    }
    sharkContainerMinimap.appendChild(mElement);
}

/**
 * Sets up the window resize handler to adjust the viewer size.
 */
window.setupWindowResizeHandler = (sharkContainerMinimap) => {
    $(window).on('resize', () => onWindowResize(sharkContainerMinimap));
    setTimeout(() => {
        onWindowResize(sharkContainerMinimap);
        s.render();
    }, 100);
};

/**
 * Loads and processes an SWC file from the given path.
 */
function loadSwcFile(swcPath, sectionArray) {
    fetch(swcPath)
        .then(response => response.text())
        .then(swcTxt => {
            try {
                const swc = swcParser(swcTxt);

                if (!swc || Object.keys(swc).length === 0) {
                    console.error("SWC parsing failed. The SWC object is empty.");
                    return;
                }

                s.swc = swc;

                const neuronData = s.loadNeuron('neuron', 'red', swc, sectionArray, true, false, true);
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
                    updateNodeAndEdgeColors(s, sectionArray);
                    setTimeout(() => adjustCameraForNeuron(s), 500);
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
 */
function loadSynapseCloud(jsonPath, maxVolumeSize) {
    console.log("Loading synapse cloud from:", jsonPath);
    fetch(jsonPath)
        .then(response => response.json())
        .then(data => {
            try {
                if (!Array.isArray(data) || data.length % 3 !== 0) {
                    console.error("JSON data is not an Array or length is not a multiple of 3.");
                    return;
                }
                console.log("Data", data);

                window.synapseColors = JSON.parse(sessionStorage.getItem("synapseColors")) || {};

                const points = [];
                for (let i = 0; i < data.length; i += 3) {
                    points.push(new THREE.Vector3(data[i], data[i + 1], data[i + 2]));
                }

                const positions = new Float32Array(points.length * 3);
                const colors = new Float32Array(points.length * 4);
                const alphas = new Float32Array(points.length);
                const sizes = new Float32Array(points.length);

                const selectedSynapses = [];
                $(".image-card-btn").each(function () {
                    selectedSynapses.push($(this).attr("data_id"));
                });

                for (let i = 0; i < points.length; i++) {
                    positions[i * 3] = points[i].x + Math.random() * 50;
                    positions[i * 3 + 1] = points[i].y + Math.random() * 50;
                    positions[i * 3 + 2] = points[i].z + Math.random() * 50;

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

                    if (selectedSynapses.length > 0) {
                        sizes[i] = selectedSynapses.includes(i.toString()) ? maxVolumeSize : 10;
                        alphas[i] = selectedSynapses.includes(i.toString()) ? 0.8 : 0.1;
                    } else {
                        sizes[i] = 10;
                        alphas[i] = 0.8;
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
                    transparent: true,
                    vertexColors: true,
                });

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
 */
function updateNodeAndEdgeColors(viewer, sectionArray) {
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

    const collectSectionIndices = [];
    $(".image-card-btn").each(function () {
        collectSectionIndices.push($(this).attr("sectionIdx"));
    });

    let vertexGreyOut = [];
    let edgeGreyOut = [];
    if (collectSectionIndices.length > 0) {
        console.log("Some sections get greyed out");
        vertexGreyOut = new Float32Array(numVertices).fill(1.0);
        edgeGreyOut = new Float32Array(numVertices * 6).fill(1.0);
    } else {
        console.log("No part gets greyed out");
        vertexGreyOut = new Float32Array(numVertices).fill(0.0);
        edgeGreyOut = new Float32Array(numVertices * 6).fill(0.0);
    }

    sectionArray.forEach((nodeGroup, index) => {
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

            if (collectSectionIndices.includes(index.toString())) {
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

/**
 * Adjusts the transparency (alpha) of specific neuron sections.
 */
window.greyOutSectionsAlpha = (viewer, sectionArray, greyOutSections) => {
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
        sectionArray[sectionIndex].forEach(vertexIndex => {
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

    console.log("Length of vertexGreyOut:", vertexGreyOut.length);
    console.log("Length of edgeGreyOut:", edgeGreyOut.length);

    skeletonVertex.geometry.attributes.color.needsUpdate = true;
    skeletonEdge.geometry.attributes.color.needsUpdate = true;

    viewer.render();
};

/**
 * Updates a specific synapse's properties.
 */
window.updateSynapse = (index, newPosition = null, newColor = null, newSize = null, save_in_session = true) => {
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

    console.log("Synapse index:", index, "Position:", positions.getX(index), positions.getY(index), positions.getZ(index));

    s.render();
};

/**
 * Adjusts the camera position and settings to focus on a neuron object in the scene.
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

    if (distance < 50) distance = 50;
    if (distance > 1000000) distance = 1000000;

    console.log("Adjusting camera. Distance:", distance, "Bounding box size:", size);

    viewer.camera.position.set(center.x, center.y, center.z + distance * 0.5);
    viewer.camera.lookAt(center);
    viewer.camera.near = 1;
    viewer.camera.far = distance * 2;
    viewer.camera.updateProjectionMatrix();
}

/**
 * Adds ambient and directional lights to the given scene if they do not already exist.
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

function generateSectionColors(sectionArray) {
    const colors = [];
    const numSections = sectionArray.length;

    for (let i = 0; i < numSections; i++) {
        const hue = (i / numSections) * 1.0; // Spread colors evenly
        colors.push(new THREE.Color().setHSL(hue, 1.0, 0.4));
    }
    return colors;
}

function generateSectionMetadata(sectionArray) {
    return sectionArray.map((_, index) => ({
        "label": `Section ${index + 1}`, // Assign a readable name
        "type": index  // Unique type ID for this section
    }));
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

function createMetadataElement(metadata, colors, activeSections) {
    const metadiv = document.createElement("div");
    metadiv.id = "node_key";
    metadiv.style.position = "absolute";
    metadiv.style.top = "40px";
    metadiv.style.right = "10px";
    metadiv.style.background = "white";
    metadiv.style.border = "solid 1px #aaaaaa";
    metadiv.style.borderRadius = "5px";
    metadiv.style.padding = "5px";
    metadiv.style.fontFamily = "Arial, sans-serif";
    metadiv.style.fontSize = "12px";
    metadiv.style.maxWidth = "150px";
    metadiv.style.overflow = "auto";

    let toinnerhtml = "<strong>Neuron Sections</strong><br>";
    metadata.forEach((m, index) => {
        let cssColor = colors[index] instanceof THREE.Color
            ? `rgb(${colors[index].r * 255}, ${colors[index].g * 255}, ${colors[index].b * 255})`
            : convertToHexColor(colors[index]);

        let isActive = activeSections.includes(index)
            ? "font-weight: bold; background: rgba(229, 218, 6, 0.41);"
            : "";

        toinnerhtml += `<div style='padding: 3px; ${isActive}'>
            <span style='display: inline-block; width: 12px; height: 12px; background: ${cssColor}; margin-right: 5px; border-radius: 4px; position: relative; top: 2px;'></span>
            ${m.label}
        </div>`;
    });

    metadiv.innerHTML = toinnerhtml;
    return metadiv;
}
