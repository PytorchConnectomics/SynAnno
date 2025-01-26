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

  Object.keys(swc).forEach((key) => {
      swc[key].x -= centroid.x;
      swc[key].y -= centroid.y;
      swc[key].z -= centroid.z;
  });

  console.log(`SWC centered at: (${centroid.x.toFixed(2)}, ${centroid.y.toFixed(2)}, ${centroid.z.toFixed(2)})`);
  return swc;
}

function updateNodeAndEdgeColors(viewer, color1 = "#00FF00", color2 = "#FF0000") {
  const neuron = viewer.scene.getObjectByName('foo');
  if (!neuron) {
      console.error("Neuron not found in the scene.");
      return;
  }
  console.log("Neuron found in the scene.");
  const green = new THREE.Color(color1);
  const red = new THREE.Color(color2);

  // Update node colors
  const points = neuron.children.find(child => child.type === "Points");
  if (points) {
      console.log("Points object found in the neuron.");
      const numNodes = points.geometry.attributes.position.count;
      const newColors = [];

      for (let i = 0; i < numNodes; i++) {
          if (i < numNodes / 2) {
              newColors.push(green.r, green.g, green.b);  // First half green
          } else {
              newColors.push(red.r, red.g, red.b);  // Second half red
          }
      }

      points.geometry.setAttribute("typeColor", new THREE.Float32BufferAttribute(newColors, 3));
      points.geometry.attributes.typeColor.needsUpdate = true;
  }

  // Update edge colors (cones)
  const cones = neuron.children.find(child => child.isMesh);
  if (cones) {
      console.log("Cones found in the neuron.");
      const numEdges = cones.geometry.attributes.position.count / 3; // Each edge has 3 vertices
      const newEdgeColors = [];

      for (let i = 0; i < numEdges; i++) {
          if (i < numEdges / 2) {
              newEdgeColors.push(green.r, green.g, green.b);
              newEdgeColors.push(green.r, green.g, green.b);
              newEdgeColors.push(green.r, green.g, green.b);
          } else {
              newEdgeColors.push(red.r, red.g, red.b);
              newEdgeColors.push(red.r, red.g, red.b);
              newEdgeColors.push(red.r, red.g, red.b);
          }
      }

      cones.geometry.setAttribute("typeColor", new THREE.Float32BufferAttribute(newEdgeColors, 3));
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

              s.loadNeuron('foo', null, swc, true, false, true);
              s.render();
              console.log("SWC data loaded successfully.");

              setTimeout(() => {
                  updateNodeAndEdgeColors(s);
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
