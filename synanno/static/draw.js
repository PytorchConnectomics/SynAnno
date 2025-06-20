$(document).ready(() => {
  const canvas_curve = $("canvas.curveCanvas")[0];
  const ctx_curve = canvas_curve.getContext("2d");

  const canvas_circle_pre = $("canvas.circleCanvasPre")[0];
  const ctx_circle_pre = canvas_circle_pre.getContext("2d");

  const canvas_circle_post = $("canvas.circleCanvasPost")[0];
  const ctx_circle_post = canvas_circle_post.getContext("2d");

  let mousePosition = { x: 0, y: 0 };
  let rect_curve, rect_circle;
  let draw_mask = false, split_mask = false;
  let points = [], pointsQBez = [];
  const thickness = 10;
  const pink = "rgba(255, 0, 255, 0.7)";
  const turquoise = "rgba(21, 229, 239, 0.92)";
  let page, data_id, label;
  let pre_CRD = false, post_CRD = false;
  let x_syn_crd = null, y_syn_crd = null;

  $(".modal").on("hidden.bs.modal", () => {
    if (!$(".modal:visible").length) {
      $("canvas.curveCanvas, canvas.circleCanvasPre, canvas.circleCanvasPost").addClass("d-none");
    }
  });

  imageData.forEach(async (image) => {
    const page = image.Page;
    const data_id = image.Image_Index;
    const base = `-${page}-${data_id}`;
    const middle_slice = image.Middle_Slice;

    const canvas_target_image_curve = `#img-target-curve${base}`;
    const canvas_target_image_circle_pre = `#img-target-circlePre${base}`;
    const canvas_target_image_circle_post = `#img-target-circlePost${base}`;

    $.ajax({
      url: "/get_auto_curve_image/" + data_id + "/" + middle_slice,
      type: 'HEAD',
      success: function (data, textStatus, xhr) {
        if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
          console.log("Auto curve image exists");
          $(canvas_target_image_curve).attr("src", "/get_auto_curve_image/" + data_id + "/" + middle_slice);
          $(canvas_target_image_curve).removeClass('d-none');
        }
        else if (xhr.status === 204) {  // Only execute if status is 404 (image does not exist)
          $.ajax({
            url: "/get_curve_image/" + data_id + "/" + middle_slice,
            type: 'HEAD',
            success: function (data, textStatus, xhr) {
              if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
                $(canvas_target_image_curve).attr("src", "/get_curve_image/" + data_id + "/" + middle_slice);
                $(canvas_target_image_curve).removeClass('d-none');
              }
            }
          });
        }
      }
    });

    $.ajax({
      url: "/get_circle_pre_image/" + data_id + "/" + middle_slice,
      type: "HEAD",
      success: function (data, textStatus, xhr) {
        if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
          $(new Image())
          .attr("src", "/get_circle_pre_image/" + data_id + "/" + middle_slice)
          .load(function () {
            $(canvas_target_image_circle_pre).attr("src", this.src);
          });
        $(canvas_target_image_circle_pre).removeClass("d-none");
        }
        else if (xhr.status === 204) {  // Only execute if status is 404 (image does not exist)
          $(canvas_target_image_circle_pre).addClass("d-none");
        }
      },
    });

    $.ajax({
      url: "/get_circle_post_image/" + data_id + "/" + middle_slice,
      type: "HEAD",
      success: function (data, textStatus, xhr) {
        if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
          $(new Image())
          .attr("src", "/get_circle_post_image/" + data_id + "/" + middle_slice)
          .load(function () {
            $(canvas_target_image_circle_post).attr("src", this.src);
          });
        $(canvas_target_image_circle_post).removeClass("d-none");
        }
        else if (xhr.status === 204) {  // Only execute if status is 404 (image does not exist)
          $(canvas_target_image_circle_post).addClass("d-none");
        }
      },
    });
  });

  $('[id^="drawButton-"]').click(async function () {
    [page, data_id, label] = $(this).attr("id").replace(/drawButton-/, "").split("-");
    $("#canvasButtonDrawMask").html('<i class="bi bi-pencil"></i>')
    .attr("title", "Draw Mask").prop("disabled", false);
    $("#canvasButtonPreCRD").prop("disabled", false);
    $("#canvasButtonPostCRD").prop("disabled", false);
    $("#canvasButtonFill, #canvasButtonRevise, #canvasButtonSave").prop("disabled", true);
    ctx_curve.restore();
    clear_canvas(ctx_curve, canvas_curve);
    clear_canvas(ctx_circle_pre, canvas_circle_pre);
    clear_canvas(ctx_circle_post, canvas_circle_post);
    points = [];
    pointsQBez = [];
    split_mask = false;
    draw_mask = true;
    mousePosition = { x: 0, y: 0 };
  });

  $("#canvasButtonAuto").on("click", async () => {
    try {
      $("#loading-bar").css('display', 'flex');
      $(".text-white").text("Auto generating...");
      const image = imageData.find(img => img.Page == page && img.Image_Index == data_id);
      const middle_slice = image.Middle_Slice;
      const base = `-${image.Page}-${data_id}`;
      const canvas_target_image_curve = `#img-target-curve${base}`;

      const response = await $.ajax({
        type: "POST",
        url: "/auto_annotate",
        data: { data_id: data_id },
      });

      if (response.result === "success") {
        // Check if auto-generated mask exists and update the image source
        $.ajax({
          url: "/get_auto_curve_image/" + data_id + "/" + middle_slice,
          type: 'HEAD',
          success: function (data, textStatus, xhr) {
            if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
              $(canvas_target_image_curve).attr("src", "/get_auto_curve_image/" + data_id + "/" + middle_slice);
              $(canvas_target_image_curve).removeClass('d-none');
            } else if (xhr.status === 204) {  // Only execute if status is 404 (image does not exist)
              $(canvas_target_image_curve).addClass('d-none');
            }
          }
        });
      } else {
        console.error("Auto annotation failed.");
      }
    } catch (error) {
      console.error("An error occurred during auto annotation:", error);
    } finally {
      $("#loading-bar").css('display', 'none');
    }
  });

  $("#canvasButtonPreCRD").on("click", () => {
    ctx_circle_pre.restore();
    if ($("canvas.circleCanvasPre").hasClass("d-none")) {
      clear_canvas(ctx_circle_pre, canvas_circle_pre);
      $("#imgDetails-EM-GT-circlePre").addClass("d-none");
      $("canvas.circleCanvasPre").removeClass("d-none");
      $("#canvasButtonDrawMask, #canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto").prop("disabled", true);
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
    } else {
      clear_canvas(ctx_circle_pre, canvas_circle_pre);
      $("canvas.circleCanvasPre").css("z-index", 3);
      $("canvas.circleCanvasPost").css("z-index", 2);
      $("canvas.curveCanvas").css("z-index", 1);
      $("#canvasButtonDrawMask, #canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonFill, #canvasButtonRevise, #canvasButtonSave, #canvasButtonAuto").prop("disabled", true);
      pre_CRD = true;
      post_CRD = false;
      split_mask = false;
      draw_mask = false;
    }
  });

  $("canvas.circleCanvasPre").on("click", async (e) => {
    if (pre_CRD) {
      clear_canvas(ctx_circle_pre, canvas_circle_pre);
      const pos = getXY(canvas_circle_pre, e, rect_circle);
      x_syn_crd = pos.x;
      y_syn_crd = pos.y;

      // Draw the circle
      ctx_circle_pre.fillStyle = "rgb(0, 255, 0)";
      ctx_circle_pre.beginPath();
      ctx_circle_pre.arc(x_syn_crd, y_syn_crd, 10, 0, 2 * Math.PI);
      ctx_circle_pre.fill();

      // Add a text label with modern styling
      const text = "Pre";
      const textX = x_syn_crd;
      const textY = y_syn_crd - 24;

      // Draw rounded background with semi-transparent dark tone
      ctx_circle_pre.fillStyle = "rgba(33, 37, 41, 0.85)"; // Bootstrap dark (same as Post)
      ctx_circle_pre.beginPath();
      ctx_circle_pre.roundRect(textX - 30, textY - 16, 60, 28, 6);
      ctx_circle_pre.fill();

      // Optional: soft shadow for modern depth
      ctx_circle_pre.shadowColor = "rgba(0, 0, 0, 0.3)";
      ctx_circle_pre.shadowBlur = 4;

      // Draw text with modern font and light green color
      ctx_circle_pre.fillStyle = "#b8fcb8"; // Light green, soft tone
      ctx_circle_pre.font = "600 14px 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif";
      ctx_circle_pre.textAlign = "center";
      ctx_circle_pre.textBaseline = "middle";
      ctx_circle_pre.fillText(text, textX, textY - 1); // 1px up

      // Reset shadow after use
      ctx_circle_pre.shadowColor = "transparent";
      ctx_circle_pre.shadowBlur = 0;

      save_canvas(canvas_circle_pre, "circlePre");
      $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonDrawMask, #canvasButtonAuto").prop("disabled", false);
      pre_CRD = false;
    }
  });


  $("#canvasButtonPostCRD").on("click", () => {
    ctx_circle_post.restore();
    if ($("canvas.circleCanvasPost").hasClass("d-none")) {
      clear_canvas(ctx_circle_post, canvas_circle_post);
      $("#imgDetails-EM-GT-circlePost").addClass("d-none");
      $("canvas.circleCanvasPost").removeClass("d-none");
      $("#canvasButtonDrawMask, #canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto").prop("disabled", true);
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
    } else {
      clear_canvas(ctx_circle_post, canvas_circle_post);
      $("canvas.circleCanvasPost").css("z-index", 3);
      $("canvas.circleCanvasPre").css("z-index", 2);
      $("canvas.curveCanvas").css("z-index", 1);
      $("#canvasButtonDrawMask, #canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonFill, #canvasButtonRevise, #canvasButtonSave, #canvasButtonAuto").prop("disabled", true);
      pre_CRD = false;
      post_CRD = true;
      split_mask = false;
      draw_mask = false;
    }
  });

  $("canvas.circleCanvasPost").on("click", async (e) => {
    if (post_CRD) {
      clear_canvas(ctx_circle_post, canvas_circle_post);
      const pos = getXY(canvas_circle_post, e, rect_circle);
      x_syn_crd = pos.x;
      y_syn_crd = pos.y;

      // Draw the circle
      ctx_circle_post.fillStyle = "rgb(0, 0, 255)";
      ctx_circle_post.beginPath();
      ctx_circle_post.arc(x_syn_crd, y_syn_crd, 10, 0, 2 * Math.PI);
      ctx_circle_post.fill();

      // Add a text label with modern styling
      const text = "Post";
      const textX = x_syn_crd;
      const textY = y_syn_crd - 24;

      // Draw rounded background with semi-transparent dark tone
      ctx_circle_post.fillStyle = "rgba(33, 37, 41, 0.85)";
      ctx_circle_post.beginPath();
      ctx_circle_post.roundRect(textX - 30, textY - 16, 60, 28, 6);
      ctx_circle_post.fill();

      // Optional: subtle shadow for depth
      ctx_circle_post.shadowColor = "rgba(0, 0, 0, 0.3)";
      ctx_circle_post.shadowBlur = 4;

      // Draw text with clean modern font and slightly lighter blue
      ctx_circle_post.fillStyle = "#d0ebff"; // Light Bootstrap blue-ish
      ctx_circle_post.font = "600 14px 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif";
      ctx_circle_post.textAlign = "center";
      ctx_circle_post.textBaseline = "middle";
      ctx_circle_post.fillText(text, textX, textY - 1); // nudged up by 1px

      // Reset shadow after use
      ctx_circle_post.shadowColor = "transparent";
      ctx_circle_post.shadowBlur = 0;

      save_canvas(canvas_circle_post, "circlePost");
      $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonDrawMask, #canvasButtonAuto").prop("disabled", false);
      post_CRD = false;
    }
  });


  $("#canvasButtonDrawMask").on("click", () => {
    clear_canvas(ctx_curve, canvas_curve);
    points = [];
    pointsQBez = [];
    ctx_curve.restore();
    if ($("canvas.curveCanvas").hasClass("d-none")) {
      $("#imgDetails-EM-GT-curve").addClass("d-none");
      $("#canvasButtonDrawMask")
  .html('<i class="bi bi-arrow-counterclockwise"></i>')
  .attr("title", "Reset");
      $("canvas.curveCanvas").removeClass("d-none");
      rect_curve = $("#imgDetails-EM")[0].getBoundingClientRect();
      $("canvas.curveCanvas")[0].width = rect_curve.width;
      $("canvas.curveCanvas")[0].height = rect_curve.height;
      $("canvas.curveCanvas").css("z-index", 3);
      $("canvas.circleCanvasPost").css("z-index", 2);
      $("canvas.circleCanvasPre").css("z-index", 1);
      split_mask = false;
      draw_mask = true;
      $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto").prop("disabled", true);
    } else {
      $("canvas.curveCanvas").addClass("d-none");
      $("#canvasButtonDrawMask")
  .html('<i class="bi bi-pencil"></i>')
  .attr("title", "Draw Mask");
      $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto").prop("disabled", false);
      $("#canvasButtonFill, #canvasButtonRevise, #canvasButtonSave").prop("disabled", true);
      points = [];
      pointsQBez = [];
      split_mask = false;
      draw_mask = false;
    }
  });

  $("#canvasButtonRevise").on("click", () => {
    $("#canvasButtonFill").prop("disabled", true);
    $("#canvasButtonRevise").prop("disabled", true);
    ctx_curve.save();
    ctx_curve.globalCompositeOperation = "destination-out";
    split_mask = true;
  });

  $("#canvasButtonFill").on("click", () => {
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

  $("#canvasButtonSave").on("click", async () => {
    split_mask = false;
    save_canvas(canvas_curve, "curve");
  });

  async function save_canvas(canvas, canvas_type) {
    const dataURL = canvas.toDataURL();
    const viewedInstanceSlice = parseInt($("#drawModal").data("viewed-instance-slice"));

    try {
      const response = await $.ajax({
        type: "POST",
        url: "/save_canvas",
        data: {
          imageBase64: dataURL,
          data_id: data_id,
          page: page,
          viewedInstanceSlice: viewedInstanceSlice,
          canvas_type: canvas_type,
        },
      });
      const data_json = JSON.parse(response.data);
      const base = `-${page}-${data_id}`;
      const canvas_target_image = `#img-target-${canvas_type}${base}`;

      if (canvas_type === 'curve') {
        $.ajax({
          url: "/get_curve_image/" + data_id + "/" + viewedInstanceSlice,
          type: 'HEAD',
          success: function (data, textStatus, xhr) {
            if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
              if (viewedInstanceSlice === parseInt(data_json.Middle_Slice, 10)) {
                $(new Image()).attr("src", "/get_curve_image/" + data_id + "/" + viewedInstanceSlice).on("load", function () {
                  $(canvas_target_image).attr("src", this.src);
                });
                $(canvas_target_image).removeClass('d-none');
              }
              $("#canvasButtonPreCRD, #canvasButtonPostCRD, #canvasButtonAuto").prop("disabled", false);
              $("#canvasButtonSave, #canvasButtonFill, #canvasButtonRevise").prop("disabled", true);
            }
            else if (xhr.status === 204) {
              $(canvas_target_image).addClass('d-none');
            }
          }
        });
      }

      if (canvas_type === "circlePre" || canvas_type === "circlePost") {
        const id = canvas_type === "circlePre" ? "pre" : "post";
        const coordinateResponse = await $.ajax({
          type: "POST",
          url: "/save_pre_post_coordinates",
          data: {
            x: x_syn_crd,
            y: y_syn_crd,
            z: viewedInstanceSlice,
            data_id: data_id,
            page: page,
            id: id,
          },
        });

        if (canvas_type === 'circlePre') {
          $.ajax({
            url: "/get_circle_pre_image/" + data_id + "/" + viewedInstanceSlice,
            type: "HEAD",
            success: function (data, textStatus, xhr) {
              if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
                $(new Image()).attr("src", "/get_circle_pre_image/" + data_id + "/" + viewedInstanceSlice).on("load", function () {
                  $(canvas_target_image).attr("src", this.src);
                });
                if (viewedInstanceSlice === parseInt(data_json.Middle_Slice, 10)) {
                  $(canvas_target_image).removeClass('d-none');
                } else {
                  $(canvas_target_image).addClass('d-none');
                }
              }
              else if (xhr.status === 204) {
                $(canvas_target_image).addClass('d-none');
              }
            },
          });        }

        if (canvas_type === 'circlePost') {
          $.ajax({
            url: "/get_circle_post_image/" + data_id + "/" + viewedInstanceSlice,
            type: "HEAD",
            success: function (data, textStatus, xhr) {
              if (xhr.status === 200) {  // Only execute if status is 200 (image exists)
                $(new Image()).attr("src", "/get_circle_post_image/" + data_id + "/" + viewedInstanceSlice).on("load", function () {
                  $(canvas_target_image).attr("src", this.src);
                });
                if (viewedInstanceSlice === parseInt(data_json.Middle_Slice, 10)) {
                  $(canvas_target_image).removeClass('d-none');
                } else {
                  $(canvas_target_image).addClass('d-none');
                }
              }
              else if (xhr.status === 204) {
                $(canvas_target_image).addClass('d-none');
              }
            },
          });        }
      }

      const curve_src = $(`#img-target-curve${base}`).attr('src');
      const custom_mask = curve_src.includes("curve_image");
      if (!custom_mask && viewedInstanceSlice === parseInt(data_json.Middle_Slice, 10)) {
        $(`#img-target-curve${base}`).addClass('d-none');
      }

    } catch (error) {
      console.error('An error occurred:', error);
    }
  }

  // Bind hotkeys to buttons
  $(document).on("keydown", (event) => {
    const hotkey = event.key.toLowerCase();
    const $button = $(`[data-hotkey="${hotkey}"]`);

    if ($button.length && !$button.prop("disabled")) {
      event.preventDefault();
      $button.trigger("click");
    }
  });

  $("canvas.curveCanvas").mousemove((event) => {
    if (split_mask) {
      if ((mousePosition.x != event.clientX || mousePosition.y != event.clientY) && event.buttons == 1) {
        mousePosition = { x: event.clientX, y: event.clientY };
        const pos = getXY(canvas_curve, event, rect_curve);
        const x = pos.x;
        const y = pos.y;
        ctx_curve.strokeStyle = pink;
        ctx_curve.beginPath();
        ctx_curve.ellipse(x, y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2);
        ctx_curve.stroke();
        ctx_curve.fill();
      }
    }
  });

  $("canvas.curveCanvas").on("click", (e) => {
    if (draw_mask) {
      clear_canvas(ctx_curve, canvas_curve);
      const pos = getXY(canvas_curve, e, rect_curve);
      const x = pos.x;
      const y = pos.y;
      points.push({ x, y });

      if (points.length > 2) {
        draw_quad_line(points, 3);
        $("#canvasButtonFill").prop("disabled", false);
      } else if (points.length > 1) {
        ctx_curve.lineWidth = 3;
        ctx_curve.strokeStyle = pink;

        // Draw line
        ctx_curve.beginPath();
        ctx_curve.moveTo(points[0].x, points[0].y);
        ctx_curve.lineTo(points[1].x, points[1].y);
        ctx_curve.stroke();

        // Draw turquoise points as squares (or change to circles if you prefer)
        ctx_curve.fillStyle = turquoise;
        ctx_curve.beginPath();
        ctx_curve.arc(points[0].x, points[0].y, 4, 0, Math.PI * 2);
        ctx_curve.fill();
        ctx_curve.beginPath();
        ctx_curve.arc(points[1].x, points[1].y, 4, 0, Math.PI * 2);
        ctx_curve.fill();
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

      // Deactivate buttons after spline is filled
      $("#canvasButtonFill, #canvasButtonRevise").prop("disabled", true);
    } else {
      console.log("A mask needs at least 3 points");
    }
  }

  function draw_quad_line(points, lineWidth = 3, draw_points = true) {
    ctx_curve.strokeStyle = pink;
    ctx_curve.lineWidth = lineWidth;

    ctx_curve.beginPath();
    ctx_curve.moveTo(points[0].x, points[0].y);

    for (let i = 1; i < points.length - 2; i++) {
      const xend = (points[i].x + points[i + 1].x) / 2;
      const yend = (points[i].y + points[i + 1].y) / 2;
      ctx_curve.quadraticCurveTo(points[i].x, points[i].y, xend, yend);
    }

    const i = points.length - 2;
    ctx_curve.quadraticCurveTo(points[i].x, points[i].y, points[i + 1].x, points[i + 1].y);

    ctx_curve.stroke();

    if (draw_points) {
      ctx_curve.fillStyle = turquoise;
      for (let p of points) {
        ctx_curve.beginPath();
        ctx_curve.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx_curve.fill();
      }
    }
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
