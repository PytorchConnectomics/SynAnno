$(document).ready(function () {
  // retrieve canvas and set 2D context
  var canvas_curve = $("canvas.curveCanvas")[0];
  var ctx_curve = canvas_curve.getContext("2d");

  var canvas_circle_pre = $("canvas.circleCanvasPre")[0];
  var ctx_circle_pre = canvas_circle_pre.getContext("2d");

  var canvas_circle_post = $("canvas.circleCanvasPost")[0];
  var ctx_circle_post = canvas_circle_post.getContext("2d");

  // initialize mouse position to zero
  var mousePosition = { x: 0, y: 0 };

  // initialize global rectangle variable
  var rect_curve, rect_circle;

  // turn mask drawing and splitting off at the start
  var draw_mask = false, split_mask = false;

  // global buffer for the start, end, and control points of the spline
  var points = [], pointsQBez = [];

  // init thickness
  var thickness = 20;

  // define colors
  const pink = "rgba(255, 0, 255, 0.7)";

  // init image identifiers to null
  var page, data_id, label;

  // path where to save the custom masks
  const base_mask_path = "/static/Images/Mask/";

  // init pre and post synaptic coordinates
  var pre_CRD = false, post_CRD = false;

  // make the last set coordinates globally available
  var x_syn_crd = null, y_syn_crd = null;

  // the currently viewed image in the grid view
  var pre_slice = null, post_slice = null;

  // make sure that the modal is reset every time it gets closed
  $(".modal").on("hidden.bs.modal", function () {
    if (!$(".modal:visible").length) {
      $("canvas.curveCanvas, canvas.circleCanvasPre, canvas.circleCanvasPost").addClass("d-none");
    }
  });

  // setup/reset the canvas whenever a draw button is clicked
  $('[id^="drawButton-"]').click(async function () {
    [page, data_id, label] = $(this).attr("id").replace(/drawButton-/, "").split("-");
    $("#canvasButtonDrawMask").text("Draw Mask").prop("disabled", false);
    $("#canvasButtonPreCRD").text("Pre-Synaptic CRD").prop("disabled", false);
    $("#canvasButtonPostCRD").text("Post-Synaptic CRD").prop("disabled", false);
    $("#canvasButtonAuto, #rangeSlices").prop("disabled", false);
    $("#canvasButtonFill, #canvasButtonRevise, #canvasButtonSave").prop("disabled", true);
    ctx_curve.restore();
    clear_canvas(ctx_curve, canvas_curve);
    clear_canvas(ctx_circle_pre, canvas_circle_pre);
    clear_canvas(ctx_circle_post, canvas_circle_post);
    points = [];
    pointsQBez = [];
    split_mask = false;
    draw_mask = true;
    pre_slice = null;
    post_slice = null;
    mousePosition = { x: 0, y: 0 };
  });

  // on click canvasButtonAuto call backend python function that queries a model to predict the mask
  $("#canvasButtonAuto").on("click", async function () {

    // call the backend function passing the path to the image and the custom mask
    const response = await $.ajax({
      type: "POST",
      url: "/auto_annotate",
      data: {
        page: page,
        data_id: data_id,
      },
    });
  });


  // on click activate canvas
  $("#canvasButtonPreCRD").on("click", function () {
    ctx_circle_pre.restore();
    if ($("canvas.circleCanvasPre").hasClass("d-none")) {
      clear_canvas(ctx_circle_pre, canvas_circle_pre);
      $("#imgDetails-EM-GT-circlePre").addClass("d-none");
      $("#canvasButtonPreCRD").text("Save");
      $("canvas.circleCanvasPre").removeClass("d-none");
      $("#canvasButtonDrawMask, #canvasButtonPostCRD, #canvasButtonAuto").prop("disabled", true);
      rect_circle = $("#imgDetails-EM")[0].getBoundingClientRect();
      $("canvas.circleCanvasPre")[0].width = rect_circle.width;
      $("canvas.circleCanvasPre")[0].height = rect_circle.height;
      $("canvas.circleCanvasPre").css("z-index", 3);
      $("canvas.circleCanvasPost").css("z-index", 2);
      $("canvas.curveCanvas").css("z-index", 1);
      pre_CRD = true;
      post_CRD = false;
      split_mask = false;
      draw_mask = false;
    } else if ($("#canvasButtonPreCRD").text() == "Save") {
      save_canvas(canvas_circle_pre, "circlePre");
      $("#canvasButtonPreCRD").text("Pre-Synaptic CRD");
      $("#canvasButtonPostCRD, #canvasButtonDrawMask, #canvasButtonAuto").prop("disabled", false);
      pre_CRD = false;
    } else {
      clear_canvas(ctx_circle_pre, canvas_circle_pre);
      $("canvas.circleCanvasPre").css("z-index", 3);
      $("canvas.circleCanvasPost").css("z-index", 2);
      $("canvas.curveCanvas").css("z-index", 1);
      $("#canvasButtonPreCRD").text("Save");
      $("#canvasButtonDrawMask, #canvasButtonPostCRD, #canvasButtonFill, #canvasButtonRevise, #canvasButtonSave, #canvasButtonAuto").prop("disabled", true);
      pre_CRD = true;
      post_CRD = false;
      split_mask = false;
      draw_mask = false;
    }
  });

  // on click activate canvas
  $("#canvasButtonPostCRD").on("click", function () {
    ctx_circle_post.restore();
    if ($("canvas.circleCanvasPost").hasClass("d-none")) {
      clear_canvas(ctx_circle_post, canvas_circle_post);
      $("#imgDetails-EM-GT-circlePost").addClass("d-none");
      $("#canvasButtonPostCRD").text("Save");
      $("canvas.circleCanvasPost").removeClass("d-none");
      $("#canvasButtonDrawMask, #canvasButtonPreCRD, #canvasButtonAuto").prop("disabled", true);
      rect_circle = $("#imgDetails-EM")[0].getBoundingClientRect();
      $("canvas.circleCanvasPost")[0].width = rect_circle.width;
      $("canvas.circleCanvasPost")[0].height = rect_circle.height;
      $("canvas.circleCanvasPost").css("z-index", 3);
      $("canvas.circleCanvasPre").css("z-index", 2);
      $("canvas.curveCanvas").css("z-index", 1);
      pre_CRD = false;
      post_CRD = true;
      split_mask = false;
      draw_mask = false;
    } else if ($("#canvasButtonPostCRD").text() == "Save") {
      save_canvas(canvas_circle_post, "circlePost");
      $("#canvasButtonPostCRD").text("Post-Synaptic CRD");
      $("#canvasButtonPreCRD, #canvasButtonDrawMask, #canvasButtonAuto").prop("disabled", false);
      post_CRD = false;
    } else {
      clear_canvas(ctx_circle_post, canvas_circle_post);
      $("canvas.circleCanvasPost").css("z-index", 3);
      $("canvas.circleCanvasPre").css("z-index", 2);
      $("canvas.curveCanvas").css("z-index", 1);
      $("#canvasButtonPostCRD").text("Save");
      $("#canvasButtonDrawMask, #canvasButtonPreCRD, #canvasButtonFill, #canvasButtonRevise, #canvasButtonSave, #canvasButtonAuto").prop("disabled", true);
      pre_CRD = false;
      post_CRD = true;
      split_mask = false;
      draw_mask = false;
    }
  });

  // on click activate canvas
  $("#canvasButtonDrawMask").on("click", function () {
    clear_canvas(ctx_curve, canvas_curve);
    points = [];
    pointsQBez = [];
    ctx_curve.restore();
    if ($("canvas.curveCanvas").hasClass("d-none")) {
      $("#imgDetails-EM-GT-curve").addClass("d-none");
      $("#canvasButtonDrawMask").text("Reset");
      $("canvas.curveCanvas").removeClass("d-none");
      rect_curve = $("#imgDetails-EM")[0].getBoundingClientRect();
      $("canvas.curveCanvas")[0].width = rect_curve.width;
      $("canvas.curveCanvas")[0].height = rect_curve.height;
      $("canvas.curveCanvas").css("z-index", 3);
      $("canvas.circleCanvasPost").css("z-index", 2);
      $("canvas.circleCanvasPre").css("z-index", 1);
      width_curve = canvas_curve.width;
      height = canvas_curve.height;
      split_mask = false;
      draw_mask = true;
      $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto, #rangeSlices").prop("disabled", true);
    } else {
      $("canvas.curveCanvas").css("z-index", 3);
      $("canvas.circleCanvasPost").css("z-index", 2);
      $("canvas.circleCanvasPre").css("z-index", 1);
      $("#canvasButtonFill, #canvasButtonRevise, #canvasButtonSave, #canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto, #rangeSlices").prop("disabled", true);
      points = [];
      pointsQBez = [];
      split_mask = false;
      draw_mask = true;
    }
  });

  // activate event for splitting/erasing the curve
  $("#canvasButtonRevise").on("click", function () {
    ctx_curve.save();
    ctx_curve.globalCompositeOperation = "destination-out";
    split_mask = true;
  });

  // create the mask based on the drawn spline
  $("#canvasButtonFill").on("click", function () {
    ctx_curve.restore();
    split_mask = false;
    draw_mask = false;
    if (!(pointsQBez.length > 0)) {
      fill_clip(pink, thickness, true);
    } else {
      fill_clip(pink, thickness, false);
    }
    $("#canvasButtonRevise, #canvasButtonSave").prop("disabled", false);
  });

  // save the current mask
  $("#canvasButtonSave").on("click", async function () {
    save_canvas(canvas_curve, "curve");
  });

  async function save_canvas(canvas, canvas_type) {
    const dataURL = canvas.toDataURL();
    const viewed_instance_slice = $("#rangeSlices").data("viewed_instance_slice");
    try {
      const response = await $.ajax({
        type: "POST",
        url: "/save_canvas",
        data: {
          imageBase64: dataURL,
          data_id: data_id,
          page: page,
          viewed_instance_slice: viewed_instance_slice,
          canvas_type: canvas_type,
        },
      });
      const data_json = JSON.parse(response.data);
      const base = "-" + page + "-" + data_id;
      const canvas_target_image = `#img-target-${canvas_type}${base}`;
      const coordinates = data_json.Adjusted_Bbox.join("_");
      const img_index = data_json.Image_Index;
      const img_name = `${canvas_type}_idx_${img_index}_slice_${viewed_instance_slice}_cor_${coordinates}.png`;
      const image_path = `${base_mask_path}${data_id}/${img_name}`;
      if (canvas_type === 'curve') {
        if (viewed_instance_slice === parseInt(data_json.Middle_Slice, 10)) {
          $(new Image()).attr("src", `${image_path}?${Date.now()}`).load(function () {
            $(canvas_target_image).attr("src", this.src);
          });
          $(canvas_target_image).removeClass('d-none');
        }
        if (pre_slice === parseInt(data_json.Middle_Slice, 10)) {
          $(`#img-target-circlePre${base}`).removeClass('d-none');
        }
        if (post_slice === parseInt(data_json.Middle_Slice, 10)) {
          $(`#img-target-circlePost${base}`).removeClass('d-none');
        }
        $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto, #rangeSlices").prop("disabled", false);
        $("#canvasButtonSave, #canvasButtonFill, #canvasButtonRevise").prop("disabled", true);
      }
      if (canvas_type === "circlePre" || canvas_type === "circlePost") {
        const id = canvas_type === "circlePre" ? "pre" : "post";
        const coordinateResponse = await $.ajax({
          type: "POST",
          url: "/save_pre_post_coordinates",
          data: {
            x: x_syn_crd,
            y: y_syn_crd,
            z: viewed_instance_slice,
            data_id: data_id,
            page: page,
            id: id,
          },
        });
        if (canvas_type === 'circlePre') {
          pre_slice = viewed_instance_slice;
          $(new Image()).attr("src", `${image_path}?${Date.now()}`).load(function () {
            $(canvas_target_image).attr("src", this.src);
          });
          if (pre_slice === parseInt(data_json.Middle_Slice, 10)) {
            $(`#img-target-circlePre${base}`).removeClass('d-none');
          } else {
            $(`#img-target-circlePre${base}`).addClass('d-none');
          }
        }
        if (canvas_type === 'circlePost') {
          post_slice = viewed_instance_slice;
          $(new Image()).attr("src", `${image_path}?${Date.now()}`).load(function () {
            $(canvas_target_image).attr("src", this.src);
          });
          if (post_slice === parseInt(data_json.Middle_Slice, 10)) {
            $(`#img-target-circlePost${base}`).removeClass('d-none');
          } else {
            $(`#img-target-circlePost${base}`).addClass('d-none');
          }
        }
        const curve_src = $(`#img-target-curve${base}`).attr('src');
        const curve_src_file = curve_src.split('/').pop().split('?')[0];
        const original = curve_src_file.startsWith('curve');
        if (!original) {
          const canvas_src = $(`#img-target-curve${base}`).attr("src").trim();
          $(`#img-target-curve${base}`).attr("src", canvas_src + "?" + Date.now());
          if (post_slice === parseInt(data_json.Middle_Slice, 10) || pre_slice === parseInt(data_json.Middle_Slice, 10)) {
            $(`#img-target-curve${base}`).addClass('d-none');
          }
        }
      }
    } catch (error) {
      console.error('An error occurred:', error);
    }
  }

  $("canvas.circleCanvasPre").on("click", function (e) {
    if (pre_CRD) {
      clear_canvas(ctx_circle_pre, canvas_circle_pre);
      var pos = getXY(canvas_circle_pre, e, rect_circle);
      x_syn_crd = pos.x;
      y_syn_crd = pos.y;
      ctx_circle_pre.fillStyle = "rgb(0, 255, 0)";
      ctx_circle_pre.beginPath();
      ctx_circle_pre.arc(x_syn_crd, y_syn_crd, 10, 0, 2 * Math.PI);
      ctx_circle_pre.fill();
    }
  });

  $("canvas.circleCanvasPost").on("click", function (e) {
    if (post_CRD) {
      clear_canvas(ctx_circle_post, canvas_circle_post);
      var pos = getXY(canvas_circle_post, e, rect_circle);
      x_syn_crd = pos.x;
      y_syn_crd = pos.y;
      ctx_circle_post.fillStyle = "rgb(0, 0, 255)";
      ctx_circle_post.beginPath();
      ctx_circle_post.arc(x_syn_crd, y_syn_crd, 10, 0, 2 * Math.PI);
      ctx_circle_post.fill();
    }
  });

  $("canvas.curveCanvas").mousemove(function (event) {
    if (split_mask) {
      if ((mousePosition.x != event.clientX || mousePosition.y != event.clientY) && event.buttons == 1) {
        mousePosition.x = event.clientX;
        mousePosition.y = event.clientY;
        var pos = getXY(canvas_curve, event, rect_curve);
        var x = pos.x;
        var y = pos.y;
        ctx_curve.strokeStyle = "#000";
        ctx_curve.beginPath();
        ctx_curve.moveTo(x + thickness, y);
        ctx_curve.ellipse(x, y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2);
        ctx_curve.fill();
      }
    }
  });

  $("canvas.curveCanvas").on("click", function (e) {
    if (draw_mask) {
      clear_canvas(ctx_curve, canvas_curve);
      ctx_curve.beginPath();
      var pos = getXY(canvas_curve, e, rect_curve);
      var x = pos.x;
      var y = pos.y;
      points.push({ x, y });
      if (points.length > 2) {
        draw_quad_line(points, 3);
        $("#canvasButtonFill").prop("disabled", false);
      } else if (points.length > 1) {
        ctx_curve.lineWidth = 3;
        ctx_curve.moveTo(points[0].x, points[0].y);
        ctx_curve.fillStyle = 'red';
        ctx_curve.fillRect(points[0].x, points[0].y, 4, 4);
        ctx_curve.fillRect(points[1].x, points[1].y, 4, 4);
        ctx_curve.fillStyle = 'black';
        ctx_curve.lineTo(points[0].x, points[0].y);
        ctx_curve.lineTo(points[1].x, points[1].y);
        ctx_curve.stroke();
      }
    }
  });

  function clear_canvas(ctx, canvas) {
    ctx.beginPath();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.stroke();
  }

  function getXY(current_canvas, evt, rect) {
    return {
      x: ((evt.clientX - rect.left) / (rect.right - rect.left)) * current_canvas.width,
      y: ((evt.clientY - rect.top) / (rect.bottom - rect.top)) * current_canvas.height,
    };
  }

  function fill_clip(pink, thickness, sample = false) {
    clear_canvas(ctx_curve, canvas_curve);
    ctx_curve.beginPath();
    let pl = points.length;
    if (pl > 2) {
      let ax, ay, bx, by, cx, cy;
      if (sample) {
        ax = points[0].x;
        ay = points[0].y;
        for (let i = 1; i < pl - 2; i++) {
          cx = points[i].x;
          cy = points[i].y;
          bx = (points[i].x + points[i + 1].x) / 2;
          by = (points[i].y + points[i + 1].y) / 2;
          plotQBez(pointsQBez, Math.floor(Math.abs(ax - bx) + Math.abs(ay - by)), ax, ay, cx, cy, bx, by);
          ax = bx;
          ay = by;
        }
        bx = points[pl - 1].x;
        by = points[pl - 1].y;
        cx = points[pl - 2].x;
        cy = points[pl - 2].y;
        plotQBez(pointsQBez, Math.floor(Math.abs(ax - bx) + Math.abs(ay - by)), ax, ay, cx, cy, bx, by);
      }
      ctx_curve.save();
      let region_1 = new Path2D();
      for (let j = 0; j < pointsQBez.length; j++) {
        region_1.moveTo(pointsQBez[j].x + thickness, pointsQBez[j].y);
        region_1.ellipse(pointsQBez[j].x, pointsQBez[j].y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2);
      }
      ctx_curve.clip(region_1);
      ctx_curve.fillStyle = pink;
      ctx_curve.strokeStyle = pink;
      ctx_curve.rect(0, 0, canvas_curve.width, canvas_curve.height);
      ctx_curve.fill();
      ctx_curve.restore();
    } else {
      console.log("A mask needs at least 3 points");
    }
  }

  function draw_quad_line(points, lineWidth = 3, draw_points = true) {
    ctx_curve.beginPath();
    ctx_curve.strokeStyle = 'black';
    ctx_curve.lineWidth = lineWidth;
    ctx_curve.moveTo(points[0].x, points[0].y);
    if (draw_points) {
      ctx_curve.fillStyle = 'red';
      ctx_curve.fillRect(points[0].x, points[0].y, 4, 4);
      if (points.length < 4) {
        ctx_curve.fillRect(points[0].x, points[0].y, 4, 4);
        ctx_curve.fillRect(points[1].x, points[1].y, 4, 4);
      } else {
        ctx_curve.fillRect(points[0].x, points[0].y, 4, 4);
      }
    }
    for (i = 1; i < points.length - 2; i++) {
      var xend = (points[i].x + points[i + 1].x) / 2;
      var yend = (points[i].y + points[i + 1].y) / 2;
      ctx_curve.quadraticCurveTo(points[i].x, points[i].y, xend, yend);
      if (draw_points) {
        ctx_curve.fillRect(points[i].x, points[i].y, 4, 4);
        ctx_curve.fillRect(points[i + 1].x, points[i + 1].y, 4, 4);
      }
    }
    ctx_curve.quadraticCurveTo(points[i].x, points[i].y, points[i + 1].x, points[i + 1].y);
    if (draw_points) {
      ctx_curve.fillRect(points[i + 1].x, points[i + 1].y, 4, 4);
    }
    ctx_curve.stroke();
  }

  function _getQBezierValue(t, p1, p2, p3) {
    var iT = 1 - t;
    return iT * iT * p1 + 2 * iT * t * p2 + t * t * p3;
  }

  function getQuadraticCurvePoint(startX, startY, cpX, cpY, endX, endY, position) {
    return {
      x: _getQBezierValue(position, startX, cpX, endX),
      y: _getQBezierValue(position, startY, cpY, endY),
    };
  }

  function plotQBez(pointsQBez, ptCount, Ax, Ay, Cx, Cy, Bx, By) {
    pointsQBez.push({ x: Ax, y: Ay });
    for (var i = 1; i < ptCount; i++) {
      var t = i / ptCount;
      pointsQBez.push(getQuadraticCurvePoint(Ax, Ay, Cx, Cy, Bx, By, t));
    }
    pointsQBez.push({ x: Bx, y: By });
    return pointsQBez;
  }
});
