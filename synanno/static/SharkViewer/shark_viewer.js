import {
    NODE_PARTICLE_IMAGE,
    stretch,
    stretch_inv,
    swcParser,
    Color,
  } from "./utils.js";

  import { BokehShader } from "../shaders/BokehShader.js";
  import { ParticleShader } from "../shaders/ParticleShader.js";
  import { ConeShader } from "../shaders/ConeShader.js";
  import { ParticleDepthShader } from "../shaders/ParticleDepthShader.js";
  import { ConeDepthShader } from "../shaders/ConeDepthShader.js";

  import OrbitUnlimitedControls from "./OrbitUnlimitedControls.js";

  //import * as THREE from "three";

  export { swcParser, stretch, stretch_inv, Color };

  const DEFAULT_POINT_THRESHOLD = 150;
  const DEFAULT_LINE_THRESHOLD = 100;

  function convertToHexColor(i) {
    let result = "#000000";
    if (i >= 0 && i <= 15) {
      result = `#00000${i.toString(16)}`;
    } else if (i >= 16 && i <= 255) {
      result = `#0000${i.toString(16)}`;
    } else if (i >= 256 && i <= 4095) {
      result = `#000${i.toString(16)}`;
    } else if (i >= 4096 && i <= 65535) {
      result = `#00${i.toString(16)}`;
    } else if (i >= 65536 && i <= 1048575) {
      result = `#0${i.toString(16)}`;
    } else if (i >= 1048576 && i <= 16777215) {
      result = `#${i.toString(16)}`;
    }
    return result;
  }

  export function calculateBoundingBox(swcJSON) {
    const boundingBox = {
      xmin: Infinity,
      xmax: -Infinity,
      ymin: Infinity,
      ymax: -Infinity,
      zmin: Infinity,
      zmax: -Infinity,
    };

    Object.values(swcJSON).forEach((node) => {
      const r = node.radius;
      if (node.x - r < boundingBox.xmin) {
        boundingBox.xmin = node.x - r;
      }
      if (node.x + r > boundingBox.xmax) {
        boundingBox.xmax = node.x + r;
      }
      if (node.y - r < boundingBox.ymin) {
        boundingBox.ymin = node.y - r;
      }
      if (node.y + r > boundingBox.ymax) {
        boundingBox.ymax = node.y + r;
      }
      if (node.z - r < boundingBox.zmin) {
        boundingBox.zmin = node.z - r;
      }
      if (node.z + r > boundingBox.zmax) {
        boundingBox.zmax = node.z + r;
      }
    });

    return boundingBox;
  }

  export function calculateBoundingSphere(swcJSON, boundingBox) {
    // Similar to:
    // "An Efficient Bounding Sphere", by Jack Ritter from "Graphics Gems", Academic Press, 1990
    // https://github.com/erich666/GraphicsGems/blob/master/gems/BoundSphere.c

    // Start with the sphere inscribed in the bounding box.  It may miss some nodes.
    const rx = (boundingBox.xmax - boundingBox.xmin) / 2;
    const ry = (boundingBox.ymax - boundingBox.ymin) / 2;
    const rz = (boundingBox.zmax - boundingBox.zmin) / 2;
    let radius = Math.min(rx, ry, rz);
    let center = new THREE.Vector3(
      boundingBox.xmin + rx,
      boundingBox.ymin + ry,
      boundingBox.zmin + rz
    );

    // Find each node that is outside the current bounding sphere.
    let radiusSq = radius * radius;
    Object.values(swcJSON).forEach((node) => {
      const nodeCenter = new THREE.Vector3(node.x, node.y, node.z);
      const nodeCenterToCenter = new THREE.Vector3();
      nodeCenterToCenter.subVectors(center, nodeCenter);
      const distSqNodeCenterToCenter = nodeCenterToCenter.dot(nodeCenterToCenter);
      // Include the node's radius when checking whether it is outside.
      if (distSqNodeCenterToCenter + node.radius * node.radius > radiusSq) {
        // If it is outside, then the new boundingp-sphere radius is the average of the old radius
        // and the distance from the outside of the node (i.e., include its radius) to the
        // old bounding-sphere center.
        const distNodeCenterToCenter = Math.sqrt(distSqNodeCenterToCenter);
        const newRadius = (radius + (distNodeCenterToCenter + node.radius)) / 2.0;
        // The new bounding sphere center will be on the line between the node and the old center.
        const nodeCenterToCenterUnit = nodeCenterToCenter
          .clone()
          .divideScalar(distNodeCenterToCenter);
        const nodeCenterToNewCenter = nodeCenterToCenterUnit
          .clone()
          .multiplyScalar(newRadius - node.radius);
        center = nodeCenter.clone().add(nodeCenterToNewCenter);
        radius = newRadius;
        radiusSq = radius * radius;
      }
    });

    return { center, radius };
  }

  /**
   * Calculate the camera position on the edge of the bounding sphere
   * @param {number} fov - the field of view for the scene
   * @param {Object} boundingSphere - object describing radius and center point of the sphere
   * @param {boolean} frontToBack - if true, then look down the Z-stack from point 0
   * @returns {Object} THREE.Vector3 object used to position the camera
   */
  export function calculateCameraPosition(
    fov,
    boundingSphere,
    frontToBack,
    maxVolumeSize
  ) {
    const theta = (fov * (Math.PI / 180.0)) / 2.0;
    const d = boundingSphere.radius / Math.sin(theta);
    const { center } = boundingSphere;
    // If negative z is greater than the .maxVolumeSize, the camera will
    // get stuck at that point and wont be able to dolly in or out. Forcing
    // the z position to be at least half the negative maxVolumeSize seems
    // to fix the issue.
    const z = Math.max(
      -(maxVolumeSize / 2),
      frontToBack ? center.z - d : center.z + d
    );
    return new THREE.Vector3(center.x, center.y, z);
  }

  // generates particle vertices
  function generateParticle(node) {
    return new THREE.Vector3(node.x, node.y, node.z);
  }

  function createMetadataElement(metadata, colors) {
    const metadiv = document.createElement("div");
    metadiv.id = "node_key";
    metadiv.style.position = "absolute";
    metadiv.style.top = "0px";
    metadiv.style.right = "10px";
    metadiv.style.border = "solid 1px #aaaaaa";
    metadiv.style.borderRadius = "5px";
    metadiv.style.padding = "2px";

    let toinnerhtml = "";
    metadata.forEach((m) => {
      const mtype = parseInt(m.type, 10);
      const threeColor = mtype < colors.length ? colors[mtype] : colors[0];
      let cssColor = threeColor;
      if (typeof threeColor !== "string")
        cssColor = convertToHexColor(threeColor);
      toinnerhtml += `<div><span style='height:10px;width:10px;background:${cssColor};`;
      toinnerhtml += `display:inline-block;'></span> : ${m.label}</div>`;
    });
    metadiv.innerHTML = toinnerhtml;
    return metadiv;
  }

  export default class SharkViewer {
    /* swc neuron json object:
     *{
     *  id : {
     *    type: <label of node (string)>,
     *    x: <x position of node (float)>,
     *    y: <y position of node (float)>,
     *    z: <z position of node (float)>,
     *    parent: <id number of node's parent (-1 if no parent)>,
     *    radius: <radius of node (float)>,
     *  }
     *}
     */
    constructor(args) {
      this.swc = null;
      // flip y axis
      this.flip = false;
      // color array, nodes of type 0 show as first color, etc.
      this.colors = [
        0x31ffdc, 0x6d4ff3, 0xaa3af0, 0xf38032, 0x59fc20, 0xf8d43c, 0xfd2c4d,
        0xc9c9c9,
      ];
      this.radius_scale_factor = 1;
      this.metadata = false;
      this.on_select_node = null;
      this.on_toggle_node = null;
      this.show_stats = false;
      this.animated = false;
      this.three = THREE;

      this.showAxes = false;
      this.show_cones = true;
      this.brainboundingbox = null;
      this.last_anim_timestamp = null;
      this.mouseHandler = null;
      this.nodeParticleTexture = NODE_PARTICLE_IMAGE;
      this.min_radius = null;
      this.raycaster = new THREE.Raycaster();
      this.trackControls = null;
      this.backgroundColor = 0xffffff;
      this.renderer = null;
      this.camera = null;
      this.cameraChangeCallback = null;
      this.onTop = false;
      this.maxVolumeSize = 100000;
      this.minLabel = 1000000000;
      this.maxLabel = 0.0;
      this.lineClick = null;
      this.motifQuery = null;

      this.effectController = { enabled: false };
      this.postprocessing = { enabled: false };
      this.shaderSettings = {
        rings: 3,
        samples: 4,
      };

      this.setValues(args);
      // anything after the above line can not be set by the caller.

      // html element that will receive webgl canvas
      if (typeof args.dom_element === "object") {
        this.dom_element = args.dom_element;
      } else {
        this.dom_element = document.getElementById(
          args.dom_element || "container"
        );
      }

      // height of canvas
      this.HEIGHT = this.dom_element.clientHeight;
      // width of canvas
      this.WIDTH = this.dom_element.clientWidth;
    }

    initPostprocessing() {
      this.postprocessing.scene = new THREE.Scene();

      this.postprocessing.camera = new THREE.OrthographicCamera(
        window.innerWidth / -2,
        window.innerWidth / 2,
        window.innerHeight / 2,
        window.innerHeight / -2,
        -10000,
        10000
      );
      this.postprocessing.camera.position.z = 100;

      this.postprocessing.scene.add(this.postprocessing.camera);

      this.postprocessing.rtTextureDepth = new THREE.WebGLRenderTarget(
        window.innerWidth,
        window.innerHeight
      );
      this.postprocessing.rtTextureColor = new THREE.WebGLRenderTarget(
        window.innerWidth,
        window.innerHeight
      );

      const bokeh_shader = BokehShader;

      this.postprocessing.bokeh_uniforms = THREE.UniformsUtils.clone(
        bokeh_shader.uniforms
      );

      this.postprocessing.bokeh_uniforms["tColor"].value =
        this.postprocessing.rtTextureColor.texture;
      this.postprocessing.bokeh_uniforms["tDepth"].value =
        this.postprocessing.rtTextureDepth.texture;
      this.postprocessing.bokeh_uniforms["textureWidth"].value =
        window.innerWidth;
      this.postprocessing.bokeh_uniforms["textureHeight"].value =
        window.innerHeight;

      this.postprocessing.materialBokeh = new THREE.ShaderMaterial({
        uniforms: this.postprocessing.bokeh_uniforms,
        vertexShader: bokeh_shader.vertexShader,
        fragmentShader: bokeh_shader.fragmentShader,
        defines: {
          RINGS: this.shaderSettings.rings,
          SAMPLES: this.shaderSettings.samples,
        },
      });

      this.postprocessing.quad = new THREE.Mesh(
        new THREE.PlaneGeometry(window.innerWidth, window.innerHeight),
        this.postprocessing.materialBokeh
      );
      this.postprocessing.quad.position.z = -500;
      this.postprocessing.scene.add(this.postprocessing.quad);
    }

    // sets up user specified configuration
    setValues(values) {
      if (values !== undefined) {
        Object.keys(values).forEach((key) => {
          const newValue = values[key];
          if (newValue !== undefined) {
            if (key in this) {
              this[key] = newValue;
            }
          }
        });
      }
    }

    setMotifQuery(motifQuery) {
      this.motifQuery = motifQuery;
    }

    // calculates color based on node type
    nodeColor(node) {
      if (node.type < this.three_colors.length) {
        return this.three_colors[node.type];
      }
      return this.three_colors[0];
    }

    // generates cone properties for node, parent pair
    generateCone(node, nodeParent, color) {
      const coneChild = {};
      const coneParent = {};

      let nodeColor = this.nodeColor(node);
      if (color) {
        nodeColor = new THREE.Color(color);
      }
      coneChild.vertex = new THREE.Vector3(node.x, node.y, node.z);
      coneChild.radius = node.radius;
      coneChild.color = nodeColor;

      let nodeParentColor = this.nodeColor(nodeParent);
      if (color) {
        nodeParentColor = new THREE.Color(color);
      }
      coneParent.vertex = new THREE.Vector3(
        nodeParent.x,
        nodeParent.y,
        nodeParent.z
      );
      coneParent.radius = nodeParent.radius;
      coneParent.color = nodeParentColor;

      // normals
      const n1 = new THREE.Vector3().subVectors(
        coneParent.vertex,
        coneChild.vertex
      );
      const n2 = n1.clone().negate();

      return {
        child: coneChild,
        parent: coneParent,
        normal1: n1,
        normal2: n2,
      };
    }

    getMotifPathThreshold() {
      return this.maxLabel / (this.maxLabel - this.minLabel);
    }

    getAbstractionBoundary(threshold) {
      return this.minLabel + (1 - threshold) * (this.maxLabel - this.minLabel);
    }

    greyNonMotifBranches(grey) {
      this.scene.traverse(function (node) {
        if (
          typeof node.name === "string" &&
          node.name.includes("skeleton-vertex")
        ) {
          // insert your code here, for example:
          node.material.uniforms.grey_out.value = grey ? 1 : 0;
        }
        if (
          typeof node.name === "string" &&
          node.name.includes("skeleton-edge")
        ) {
          // insert your code here, for example:
          node.material.uniforms.grey_out.value = grey ? 1 : 0;
        }
      });
    }

    /**
     * Set neuron abstraction threshold
     * @param threshold value between 0 and 1. 0: nothing is abstracted, 1: everything is abstracted
     */
    setAbstractionThreshold(threshold) {
      if (0 <= threshold && threshold <= 1) {
        let boundary = this.getAbstractionBoundary(threshold);
        this.scene.traverse(function (node) {
          if (
            typeof node.name === "string" &&
            node.name.includes("skeleton-vertex")
          ) {
            // insert your code here, for example:
            node.material.uniforms.abstraction_threshold.value = boundary;
          }
          if (
            typeof node.name === "string" &&
            node.name.includes("skeleton-edge")
          ) {
            // insert your code here, for example:
            node.material.uniforms.abstraction_threshold.value = boundary;
          }
        });
      }
    }

    setColor(neuron, color) {
      if (neuron.isNeuron) {
        console.log("setColor", neuron.name, color);

        neuron.children.forEach((child) => {
          if (
            typeof child.name === "string" &&
            child.name.includes("skeleton-vertex")
          ) {
            // insert your code here, for example:
            child.material.uniforms.color.value = new THREE.Color(color);
          }
          if (
            typeof child.name === "string" &&
            child.name.includes("skeleton-edge")
          ) {
            // insert your code here, for example:
            child.material.uniforms.color.value = new THREE.Color(color);
          }
        });
      }
    }

    createNeuron(name, swcJSON, color = undefined) {
      // neuron is object 3d which ensures all components move together
      const neuron = new THREE.Object3D();
      let normalized_motif_path_position = 0.5;

      neuron.color = color;
      const image = document.createElement("img");
      const sphereImg = new THREE.Texture(image);
      image.onload = function onload() {
        sphereImg.needsUpdate = true;
      };
      image.src = this.nodeParticleTexture;

      let geometry = new THREE.BufferGeometry();
      const particleScale =
        (0.2 * this.HEIGHT) /
        //this.renderer.getPixelRatio() /
        Math.tan((0.28 * this.fov * Math.PI) / 180.0);

      console.log("particle scale: ", particleScale);

      const customAttributes = {
        radius: { type: "fv1", value: [] },
        vertices: { type: "f", value: [] },
        label: { type: "fv1", value: [] },
      };

      let threshold = Object.assign({}, this.maxLabel);

      const indexLookup = {};

      let particleShader = structuredClone(ParticleShader);

      particleShader.uniforms["sphereTexture"].value = sphereImg;
      particleShader.uniforms["particleScale"].value = particleScale;
      particleShader.uniforms["color"].value = new THREE.Color(color);
      particleShader.uniforms["abstraction_threshold"].value = threshold;
      particleShader.uniforms["grey_out"].value = 0;

      let material = new THREE.ShaderMaterial({
        uniforms: particleShader.uniforms,
        vertexShader: particleShader.vertexShader,
        fragmentShader: particleShader.fragmentShader,
        transparent: true,
      });

      let particleDepthShader = structuredClone(ParticleDepthShader);

      particleDepthShader.uniforms.mNear.value = this.camera.near;
      particleDepthShader.uniforms.mFar.value = this.camera.far;
      particleDepthShader.uniforms.sphereTexture.value = sphereImg;
      particleDepthShader.uniforms.particleScale.value = particleScale;

      neuron.particleMaterialDepth = new THREE.ShaderMaterial({
        uniforms: particleDepthShader.uniforms,
        vertexShader: particleDepthShader.vertexShader,
        fragmentShader: particleDepthShader.fragmentShader,
      });

      Object.keys(swcJSON).forEach((node) => {
        const particleVertex = generateParticle(swcJSON[node]);

        let radius = swcJSON[node].radius * this.radius_scale_factor;
        let label = swcJSON[node].type;

        if (label < this.minLabel) {
          this.minLabel = label;
        }
        if (label > this.maxLabel) {
          this.maxLabel = label;
        }

        normalized_motif_path_position = this.getMotifPathThreshold();

        if (this.min_radius && radius < this.min_radius) {
          radius = this.min_radius;
        }

        customAttributes.radius.value.push(radius);
        customAttributes.vertices.value.push(particleVertex.x);
        customAttributes.vertices.value.push(particleVertex.y);
        customAttributes.vertices.value.push(particleVertex.z);
        customAttributes.label.value.push(label);

        indexLookup[customAttributes.radius.value.length - 1] =
          swcJSON[node].sampleNumber;
      });

      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(customAttributes.vertices.value, 3)
      );
      geometry.setAttribute(
        "radius",
        new THREE.Float32BufferAttribute(customAttributes.radius.value, 1)
      );
      geometry.setAttribute(
        "label",
        new THREE.Float32BufferAttribute(customAttributes.label.value, 1)
      );

      const particles = new THREE.Points(geometry, material);
      particles.name = "skeleton-vertex";

      let materialShader = null;

      material.onBeforeCompile = (shader) => {
        shader.uniforms.alpha = { value: 0 };
        shader.vertexShader = `uniform float alpha;\n${shader.vertexShader}`;
        shader.vertexShader = shader.vertexShader.replace(
          "#include <begin_vertex>",
          ["vAlpha = alpha"].join("\n")
        );
        materialShader = shader;
        materialShader.uniforms.alpha.value = 0.9;
        particles.userData.materialShader = materialShader;
      };

      neuron.add(particles);

      if (this.show_cones) {
        // Cone quad imposters, to link spheres together
        const coneAttributes = {
          radius: { type: "fv1", value: [] },
          indices: { type: "iv1", value: [] },
          typeColor: { type: "c", value: [] },
          vertices: { type: "f", value: [] },
          normals: { type: "f", value: [] },
          uv: { type: "f", value: [] },
          label: { type: "fv1", value: [] },
        };
        const uvs = [
          new THREE.Vector2(0.5, 0),
          new THREE.Vector2(0.5, 1),
          new THREE.Vector2(0.5, 1),
        ];
        const coneGeom = new THREE.BufferGeometry();
        let ix21 = 0;

        Object.keys(swcJSON).forEach((node) => {
          if (swcJSON[node].parent !== -1) {
            // Paint two triangles to make a cone-imposter quadrilateral
            // Triangle #1
            const cone = this.generateCone(
              swcJSON[node],
              swcJSON[swcJSON[node].parent],
              color
            );

            let parentRadius = cone.parent.radius * this.radius_scale_factor;
            if (this.min_radius && parentRadius < this.min_radius) {
              parentRadius = this.min_radius;
            }

            let childRadius = cone.child.radius * this.radius_scale_factor;
            if (this.min_radius && childRadius < this.min_radius) {
              childRadius = this.min_radius;
            }

            let label = swcJSON[node].type;

            // vertex 1
            coneAttributes.vertices.value.push(cone.child.vertex.x);
            coneAttributes.vertices.value.push(cone.child.vertex.y);
            coneAttributes.vertices.value.push(cone.child.vertex.z);
            coneAttributes.radius.value.push(childRadius);
            coneAttributes.normals.value.push(cone.normal1.x);
            coneAttributes.normals.value.push(cone.normal1.y);
            coneAttributes.normals.value.push(cone.normal1.z);
            coneAttributes.uv.value.push(uvs[0].x);
            coneAttributes.uv.value.push(uvs[0].y);
            coneAttributes.indices.value.push(ix21);
            coneAttributes.label.value.push(label);
            ix21 += 1;

            // vertex 2
            coneAttributes.vertices.value.push(cone.child.vertex.x);
            coneAttributes.vertices.value.push(cone.child.vertex.y);
            coneAttributes.vertices.value.push(cone.child.vertex.z);
            coneAttributes.radius.value.push(childRadius);
            coneAttributes.normals.value.push(cone.normal2.x);
            coneAttributes.normals.value.push(cone.normal2.y);
            coneAttributes.normals.value.push(cone.normal2.z);
            coneAttributes.uv.value.push(uvs[1].x);
            coneAttributes.uv.value.push(uvs[1].y);
            coneAttributes.indices.value.push(ix21);
            coneAttributes.label.value.push(label);
            ix21 += 1;

            // vertex 3
            coneAttributes.vertices.value.push(cone.parent.vertex.x);
            coneAttributes.vertices.value.push(cone.parent.vertex.y);
            coneAttributes.vertices.value.push(cone.parent.vertex.z);
            coneAttributes.radius.value.push(parentRadius);
            coneAttributes.normals.value.push(cone.normal2.x);
            coneAttributes.normals.value.push(cone.normal2.y);
            coneAttributes.normals.value.push(cone.normal2.z);
            coneAttributes.uv.value.push(uvs[2].x);
            coneAttributes.uv.value.push(uvs[2].y);
            coneAttributes.indices.value.push(ix21);
            coneAttributes.label.value.push(label);
            ix21 += 1;

            // vertex 1
            coneAttributes.vertices.value.push(cone.parent.vertex.x);
            coneAttributes.vertices.value.push(cone.parent.vertex.y);
            coneAttributes.vertices.value.push(cone.parent.vertex.z);
            coneAttributes.radius.value.push(parentRadius);
            coneAttributes.normals.value.push(cone.normal1.x);
            coneAttributes.normals.value.push(cone.normal1.y);
            coneAttributes.normals.value.push(cone.normal1.z);
            coneAttributes.uv.value.push(uvs[0].x);
            coneAttributes.uv.value.push(uvs[0].y);
            coneAttributes.indices.value.push(ix21);
            coneAttributes.label.value.push(label);
            ix21 += 1;

            // vertex 2
            coneAttributes.vertices.value.push(cone.parent.vertex.x);
            coneAttributes.vertices.value.push(cone.parent.vertex.y);
            coneAttributes.vertices.value.push(cone.parent.vertex.z);
            coneAttributes.radius.value.push(parentRadius);
            coneAttributes.normals.value.push(cone.normal2.x);
            coneAttributes.normals.value.push(cone.normal2.y);
            coneAttributes.normals.value.push(cone.normal2.z);
            coneAttributes.uv.value.push(uvs[1].x);
            coneAttributes.uv.value.push(uvs[1].y);
            coneAttributes.indices.value.push(ix21);
            coneAttributes.label.value.push(label);
            ix21 += 1;

            // vertex 3
            coneAttributes.vertices.value.push(cone.child.vertex.x);
            coneAttributes.vertices.value.push(cone.child.vertex.y);
            coneAttributes.vertices.value.push(cone.child.vertex.z);
            coneAttributes.radius.value.push(childRadius);
            coneAttributes.normals.value.push(cone.normal1.x);
            coneAttributes.normals.value.push(cone.normal1.y);
            coneAttributes.normals.value.push(cone.normal1.z);
            coneAttributes.uv.value.push(uvs[2].x);
            coneAttributes.uv.value.push(uvs[2].y);
            coneAttributes.indices.value.push(ix21);
            coneAttributes.label.value.push(label);
            ix21 += 1;
          }
        });
        coneGeom.setIndex(
          new THREE.Uint32BufferAttribute(coneAttributes.indices.value, 1)
        );
        coneGeom.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(coneAttributes.vertices.value, 3)
        );
        coneGeom.setAttribute(
          "radius",
          new THREE.Float32BufferAttribute(coneAttributes.radius.value, 1)
        );
        coneGeom.setAttribute(
          "normal",
          new THREE.Float32BufferAttribute(coneAttributes.normals.value, 3)
        );
        coneGeom.setAttribute(
          "uv",
          new THREE.Float32BufferAttribute(coneAttributes.uv.value, 2)
        );
        coneGeom.setAttribute(
          "label",
          new THREE.Float32BufferAttribute(coneAttributes.label.value, 1)
        );

        let coneShader = structuredClone(ConeShader);

        coneShader.uniforms["sphereTexture"].value = sphereImg;
        coneShader.uniforms["color"].value = new THREE.Color(color);
        coneShader.uniforms["abstraction_threshold"].value = threshold;
        coneShader.uniforms["grey_out"].value = 0;

        const coneMaterial = new THREE.ShaderMaterial({
          uniforms: coneShader.uniforms,
          vertexShader: coneShader.vertexShader,
          fragmentShader: coneShader.fragmentShader,
          transparent: true,
          depthTest: true,
          side: THREE.DoubleSide,
          alphaTest: 0.5,
        });

        let coneDepthShader = structuredClone(ConeDepthShader);
        coneDepthShader.uniforms.mNear.value = this.camera.near;
        coneDepthShader.uniforms.mFar.value = this.camera.far;
        coneDepthShader.uniforms.sphereTexture.value = sphereImg;

        neuron.coneMaterialDepth = new THREE.ShaderMaterial({
          uniforms: coneDepthShader.uniforms,
          vertexShader: coneDepthShader.vertexShader,
          fragmentShader: coneDepthShader.fragmentShader,
          transparent: true,
          depthTest: true,
          side: THREE.DoubleSide,
          alphaTest: 0.5,
        });

        const coneMesh = new THREE.Mesh(coneGeom, coneMaterial);
        coneMesh.name = "skeleton-edge";

        coneMaterial.onBeforeCompile = (shader) => {
          // console.log( shader )
          shader.uniforms.alpha = { value: 0 };
          shader.vertexShader = `uniform float alpha;\n${shader.vertexShader}`;
          shader.vertexShader = shader.vertexShader.replace(
            "#include <begin_vertex>",
            ["vAlpha = alpha"].join("\n")
          );
          materialShader = shader;

          materialShader.uniforms.alpha.value = 0.9;

          coneMesh.userData = { materialShader };
        };

        neuron.add(coneMesh);
      }
      return [neuron, normalized_motif_path_position];
    }

    // copied from example at http://jsfiddle.net/b97zd1a3/16/
    addAxes() {
      const CANVAS_WIDTH = 200;
      const CANVAS_HEIGHT = 200;
      const axesRenderer = new THREE.WebGLRenderer({ alpha: true }); // clear
      axesRenderer.setClearColor(0x000000, 0);
      axesRenderer.setSize(CANVAS_WIDTH, CANVAS_HEIGHT);
      this.axesRenderer = axesRenderer;

      const axesCanvas = this.dom_element.appendChild(axesRenderer.domElement);
      axesCanvas.setAttribute("id", "axesCanvas");
      axesCanvas.style.width = CANVAS_WIDTH;
      axesCanvas.style.height = CANVAS_HEIGHT;
      axesCanvas.style.position = "absolute";
      axesCanvas.style.zIndex = 200;
      axesCanvas.style.bottom = "5px";
      axesCanvas.style.right = "5px";

      const axesCamera = new THREE.PerspectiveCamera(
        50,
        CANVAS_WIDTH / CANVAS_HEIGHT,
        1,
        1000
      );
      axesCamera.up = this.camera.up; // important!
      this.axesCamera = axesCamera;

      const axesScene = new THREE.Scene();
      const axesPos = new THREE.Vector3(0, 0, 0);
      axesScene.add(
        new THREE.ArrowHelper(
          new THREE.Vector3(1, 0, 0),
          axesPos,
          60,
          0xff0000,
          20,
          10
        )
      );
      axesScene.add(
        new THREE.ArrowHelper(
          new THREE.Vector3(0, 1, 0),
          axesPos,
          60,
          0x00ff00,
          20,
          10
        )
      );
      axesScene.add(
        new THREE.ArrowHelper(
          new THREE.Vector3(0, 0, 1),
          axesPos,
          60,
          0x0000ff,
          20,
          10
        )
      );
      this.axesScene = axesScene;
    }

    // Sets up three.js scene
    init() {
      // // set up colors and materials based on color array
      this.three_colors = [];
      Object.keys(this.colors).forEach((color) => {
        this.three_colors.push(new THREE.Color(this.colors[color]));
      });

      // setup render
      this.renderer = new THREE.WebGLRenderer({
        antialias: true, // to get smoother output
      });
      this.renderer.setClearColor(this.backgroundColor, 1);
      this.renderer.setSize(this.WIDTH, this.HEIGHT);
      this.dom_element.appendChild(this.renderer.domElement);

      // to let on-top rendering work
      this.renderer.autoClear = false;

      // create a scene
      this.scene = new THREE.Scene();

      // put a camera in the scene
      this.fov = 45;
      const cameraPosition = this.maxVolumeSize;
      const farClipping = 120000;
      const nearClipping = 1;
      this.camera = new THREE.PerspectiveCamera(
        this.fov,
        this.WIDTH / this.HEIGHT,
        nearClipping,
        farClipping
      );

      this.camera.position.z = farClipping;

      if (this.showAxes) {
        this.addAxes();
      }

      if (this.flip === true) {
        this.camera.up.setY(-1);
      }

      if (this.swc) {
        const [neuron, motif_path] = this.createNeuron(this.swc);
        const boundingBox = calculateBoundingBox(this.swc);
        const boundingSphere = calculateBoundingSphere(this.swc, boundingBox);
        // store neuron status and bounding sphere for later use
        // when resetting the view.
        neuron.isNeuron = true;
        neuron.boundingSphere = boundingSphere;
        this.scene.add(neuron);
      }

      // for elements that may be rendered on top
      this.sceneOnTopable = new THREE.Scene();

      if (this.metadata) {
        const mElement = createMetadataElement(this.metadata, this.colors);
        this.dom_element.appendChild(mElement);
      }

      this.trackControls = new OrbitUnlimitedControls(
        this.camera,
        this.dom_element
      );
      this.trackControls.maxDistance = cameraPosition;
      this.trackControls.minDistance = 15;
      this.trackControls.addEventListener("change", this.render.bind(this));
      // TODO: have a callback here that reports the current position of the
      // camera. That way we can store it in the state and restore from there.
      this.trackControls.addEventListener("change", () => {
        if (this.cameraChangeCallback) {
          const { position: pos } = this.camera;
          this.cameraChangeCallback({ x: pos.x, y: pos.y, z: pos.z });
        }
      });

      this.raycaster.params.Points.threshold = DEFAULT_POINT_THRESHOLD;
      this.raycaster.params.Line.threshold = DEFAULT_LINE_THRESHOLD;

      this.initPostprocessing();

      this.effectController.enabled = false;
      this.effectController.jsDepthCalculation = false;
      this.effectController.shaderFocus = false;

      this.effectController.fstop = 2.2;
      this.effectController.maxblur = 0.5;

      this.effectController.showFocus = false;
      this.effectController.focalDepth = 4;
      this.effectController.manualdof = false;
      this.effectController.vignetting = true;
      this.effectController.depthblur = false;

      this.effectController.threshold = 0.8;
      this.effectController.gain = 2.0;
      this.effectController.bias = 0.5;
      this.effectController.fringe = 0.7;

      this.effectController.focalLength = 35;
      this.effectController.noise = false;
      this.effectController.pentagon = false;

      this.effectController.dithering = 0.0001;

      this.matChanger();
      this.shaderUpdate();
    }

    shaderUpdate() {
      this.postprocessing.materialBokeh.defines.RINGS = this.shaderSettings.rings;
      this.postprocessing.materialBokeh.defines.SAMPLES =
        this.shaderSettings.samples;
      this.postprocessing.materialBokeh.needsUpdate = true;
    }

    matChanger() {
      console.log("update params");
      for (const e in this.effectController) {
        if (e in this.postprocessing.bokeh_uniforms) {
          this.postprocessing.bokeh_uniforms[e].value = this.effectController[e];
        }
      }
      this.postprocessing.enabled = this.effectController.enabled;
      this.postprocessing.bokeh_uniforms["znear"].value = this.camera.near;
      this.postprocessing.bokeh_uniforms["zfar"].value = this.camera.far;
      this.camera.setFocalLength(this.effectController.focalLength);
    }

    cameraCoords() {
      const { position: pos } = this.camera;
      return { x: pos.x, y: pos.y, z: pos.z };
    }

    cameraTarget() {
      const { target } = this.trackControls;
      return { x: target.x, y: target.y, z: target.z };
    }

    resetView() {
      this.trackControls.reset();
      this.trackControls.update();
      this.camera.up.set(0, 1, 0);
    }

    restoreView(x = 0, y = 0, z = 0, target) {
      this.trackControls.object.position.set(x, y, z);
      if (target) {
        this.trackControls.target.set(target.x, target.y, target.z);
      }
      this.trackControls.update();
    }

    resetAroundFirstNeuron({ frontToBack } = { frontToBack: true }) {
      const neurons = this.scene.children.filter((c) => c.isNeuron);
      if (neurons.length > 0) {
        const target = neurons[0].boundingSphere.center;
        const position = calculateCameraPosition(
          this.fov,
          neurons[0].boundingSphere,
          frontToBack,
          this.maxVolumeSize
        );
        this.trackControls.update();
        this.trackControls.target.set(target.x, target.y, target.z);
        this.camera.position.set(position.x, position.y, position.z);
        this.camera.up.set(0, 1, 0);
      }
    }

    updateDofEnabled(enabled) {
      this.effectController.enabled = enabled;
      this.matChanger();
    }

    updateDofFocus(focus) {
      this.effectController.focalDepth = focus;
      this.matChanger();
    }

    updateDofBlur(blur) {
      this.effectController.maxblur = blur;
      this.matChanger();
    }

    // animation loop
    animate(timestamp = null) {
      requestAnimationFrame(this.animate.bind(this));
      this.render();
    }

    // render the scene
    render() {
      if (this.postprocessing.enabled) {
        this.renderer.clear();

        this.renderer.setRenderTarget(this.postprocessing.rtTextureColor);
        this.renderer.clear();
        this.renderer.render(this.scene, this.camera);

        this.scene.children.forEach((child, i) => {
          if (child.isNeuron) {
            this.scene.overrideMaterial = child.particleMaterialDepth;
            this.renderer.setRenderTarget(this.postprocessing.rtTextureDepth);
            //this.renderer.setRenderTarget(null);
            this.renderer.clear();
            this.renderer.render(this.scene, this.camera);
            if (this.show_cones) {
              this.scene.overrideMaterial = child.coneMaterialDepth;
              this.renderer.setRenderTarget(this.postprocessing.rtTextureDepth);
              this.renderer.clear();
              this.renderer.render(this.scene, this.camera);
            }
            this.scene.overrideMaterial = null;
          }
        });
        this.renderer.setRenderTarget(null);
        this.renderer.render(
          this.postprocessing.scene,
          this.postprocessing.camera
        );
      } else {
        this.scene.overrideMaterial = null;
        this.renderer.setRenderTarget(null);
        this.renderer.clear();
        this.renderer.render(this.scene, this.camera);
      }
    }

    /**
     * Load a neuron from an swc file into the current scene.
     * @param {string} filename - unique name for the neuron
     * @param {?string} color - hexadecimal string to set the color of the neuron
     * @param {JSON} nodes - JSON string generated from swcParser
     * @param {boolean} [updateCamera=true] - Should the camera position update
     * after the neuron is added to the scene.
     * @param {boolean} [onTopable=false] - If true, the neuron will be rendered
     * on top of (i.e., not occluded by) other neurons that had onTopable=false
     * @param {boolean} [frontToBack=false] - if true, then look down the Z-stack from point 0
     * @returns {null}
     */
    loadNeuron(
      filename,
      color,
      nodes,
      updateCamera = true,
      onTopable = false,
      frontToBack = false
    ) {
      const [neuron, motif_path] = this.createNeuron(filename, nodes, color);
      const boundingBox = calculateBoundingBox(nodes);
      const boundingSphere = calculateBoundingSphere(nodes, boundingBox);
      const target = boundingSphere.center;
      const position = calculateCameraPosition(
        this.fov,
        boundingSphere,
        frontToBack,
        this.maxVolumeSize
      );

      if (updateCamera) {
        this.trackControls.update();
        this.trackControls.target.set(target.x, target.y, target.z);
        this.camera.position.set(position.x, position.y, position.z);
      }

      neuron.name = filename;
      neuron.isNeuron = true;
      neuron.boundingSphere = boundingSphere;
      return [neuron, motif_path];
    }

    // use onTopable=true to correspond to loadNeuron(..., onTopable=true)
    neuronLoaded(filename, onTopable = false) {
      const scene = onTopable ? this.sceneOnTopable : this.scene;
      return scene.getObjectByName(filename) !== undefined;
    }

    // use onTopable=true to correspond to loadNeuron(..., onTopable=true)
    unloadNeuron(filename, onTopable = false) {
      const scene = onTopable ? this.sceneOnTopable : this.scene;
      const neuron = scene.getObjectByName(filename);
      scene.remove(neuron);
    }

    setNeuronVisible(id, visible, onTopable = false) {
      const scene = onTopable ? this.sceneOnTopable : this.scene;
      const neuron = scene.getObjectByName(id);
      if (neuron) {
        neuron.visible = visible;
      }
    }

    setSize(width, height) {
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();

      this.renderer.setSize(width, height);

      this.HEIGHT = height;
      this.WIDTH = width;
    }

    setBackground(color) {
      this.backgroundColor = color;
      this.renderer.setClearColor(this.backgroundColor, 1);
    }
  }
