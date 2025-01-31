function centerSWC(swc) {
  if (!swc || Object.keys(swc).length === 0) {
      console.error("Invalid or empty SWC data.");
      return swc;
  }

  let sumX = 0, sumY = 0, sumZ = 0, count = 0;

  for (const node of Object.values(swc)) {
      sumX += node.x || 0;
      sumY += node.y || 0;
      sumZ += node.z || 0;
      count++;
  }

  if (count === 0) {
      console.error("SWC contains no nodes.");
      return swc;
  }

  const centroid = {
      x: sumX / count,
      y: sumY / count,
      z: sumZ / count
  };

  for (const key in swc) {
      swc[key].x -= centroid.x;
      swc[key].y -= centroid.y;
      swc[key].z -= centroid.z;
  }

  console.log(`SWC centered at:
    X: ${centroid.x.toFixed(2)},
    Y: ${centroid.y.toFixed(2)},
    Z: ${centroid.z.toFixed(2)}`);
  return swc;
}

function updateNodeAndEdgeColors(viewer, neuron_section, color1 = "#00FF00", color2 = "#FF0000") {
    const neuron = viewer.scene.getObjectByName('foo');

    if (!neuron) {
        console.error("Neuron not found in the scene.");
        return;
    }

    console.log("Neuron found in the scene.");

    const highlightColor = new THREE.Color(color1);
    const defaultColor = new THREE.Color(color2);

    // Convert neuron_section to a Set for quick lookup
    const neuronSet = new Set(neuron_section);

    // Get the Points object (nodes)
    const points = neuron.children.find(child => child.type === "Points");

    if (points) {
        console.log("Points object found in the neuron.");

        const indexLookup = {};
        Object.keys(points.userData.indexLookup).forEach(key => {
            indexLookup[parseInt(key)] = points.userData.indexLookup[key];
        });

        const numNodes = points.geometry.attributes.position.count;
        const newColors = [];

        for (let i = 0; i < numNodes; i++) {
            const nodeID = indexLookup[i];

            if (neuronSet.has(nodeID)) {
                newColors.push(highlightColor.r, highlightColor.g, highlightColor.b);
            } else {
                newColors.push(defaultColor.r, defaultColor.g, defaultColor.b);
            }
        }

        points.geometry.setAttribute("typeColor", new THREE.Float32BufferAttribute(newColors, 3));
        points.geometry.attributes.typeColor.needsUpdate = true;
    }

    // Get the Cones object (edges)
    const cones = neuron.children.find(child => child.isMesh);

    if (cones) {
        console.log("Cones found in the neuron.");

        const swcData = viewer.swc;  // Original SWC data (node-parent mappings)
        const edgeColors = [];

        Object.values(swcData).forEach(node => {
            if (node.parent !== -1 && swcData[node.parent]) {  // Ensure the node has a valid parent
                const parentID = node.parent;
                const childID = node.id;
                console.log(`Parent: ${parentID}, Child: ${childID}`);

                const isHighlighted = neuronSet.has(parentID) || neuronSet.has(childID);
                console.log(`IsHighlighted: ${isHighlighted}`);
                const color = isHighlighted ? highlightColor : defaultColor;

                edgeColors.push(color.r, color.g, color.b);
                edgeColors.push(color.r, color.g, color.b);
                edgeColors.push(color.r, color.g, color.b);
            }
            edgeColors.push(defaultColor.r, defaultColor.g, defaultColor.b);
            edgeColors.push(defaultColor.r, defaultColor.g, defaultColor.b);
            edgeColors.push(defaultColor.r, defaultColor.g, defaultColor.b);
        });

        cones.geometry.setAttribute("typeColor", new THREE.Float32BufferAttribute(edgeColors, 3));
        cones.geometry.attributes.typeColor.needsUpdate = true;
    }

    viewer.render();
    console.log("Node and edge colors updated.");
}

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
              swc = centerSWC(swc);
              s.swc = swc;
              s.loadNeuron('foo', null, swc, true, false, true);
              s.render();
              console.log("SWC data loaded successfully.");

            // populate indexLookup manually
            setTimeout(() => {
            const neuron = s.scene.getObjectByName('foo');
            const points = neuron.children.find(child => child.type === "Points");
            if (points) {
                console.log("Populating indexLookup manually...");
                const indexLookup = {};
                const nodeIds = Object.keys(swc).map(id => parseInt(id));

                nodeIds.forEach((nodeId, i) => {
                    indexLookup[i] = nodeId; // Map index in Points array to node ID
                });

                points.userData.indexLookup = indexLookup; // Assign it manually
            }}, 1000);

            // Update node and edge colors
            setTimeout(() => {
                updateNodeAndEdgeColors(s,Array.from(new Array(1500), (x, i) => i));
                console.log("Node colors updated.");
            }, 1000);

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
