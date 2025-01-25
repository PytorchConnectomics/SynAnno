function centerSWC(swc) {
    let sumX = 0, sumY = 0, sumZ = 0;
    let count = 0;

    // Iterate over SWC object keys to accumulate coordinates
    Object.values(swc).forEach((node) => {
      sumX += node.x;
      sumY += node.y;
      sumZ += node.z;
      count++;
    });

    if (count === 0) {
      console.error("SWC contains no nodes.");
      return swc;
    }

    // Compute centroid
    const centroid = {
      x: sumX / count,
      y: sumY / count,
      z: sumZ / count
    };

    // Translate each node to center at (0,0,0)
    Object.keys(swc).forEach((key) => {
      swc[key].x -= centroid.x;
      swc[key].y -= centroid.y;
      swc[key].z -= centroid.z;
    });

    console.log(`SWC centered to origin: (${centroid.x.toFixed(2)}, ${centroid.y.toFixed(2)}, ${centroid.z.toFixed(2)})`);
    return swc;
  }

  function readSwcFile(e) {
    const f = e.target.files[0];
    if (f) {
      const r = new FileReader();
      r.onload = (e2) => {
        const swcTxt = e2.target.result;
        let swc = sharkViewer.swcParser(swcTxt);

        if (swc && Object.keys(swc).length > 0) {
          // Center the SWC data before loading
          swc = centerSWC(swc);

          s.loadNeuron('foo', '#ff0000', swc, true, false, true);
          s.render();
        } else {
          alert("Please upload a valid SWC file.");
        }
      };
      r.readAsText(f);
    } else {
      alert("Failed to load file");
    }
  }

  window.onload = () => {
    document
      .getElementById("swc_input")
      .addEventListener("change", readSwcFile, false);

    const swc = sharkViewer.swcParser(document.getElementById("swc").text);
    mdata = JSON.parse(document.getElementById("metadata_swc").text);

    s = new sharkViewer.default({
      animated: false,
      mode: 'particle',
      dom_element: document.getElementById('container'),
      metadata: mdata,
      showAxes: 10000,
      showStats: true,
      maxVolumeSize: 5000000,
      cameraChangeCallback: () => {}
    });

    window.s = s;
    s.init();
    s.animate();

    // Center the initial SWC data before loading
    s.loadNeuron('swc', null, swc, true, false, true);
    s.render();
  };
