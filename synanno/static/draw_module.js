$(document).ready(() => {
  const currentPage = parseInt($("script[src*='draw_module.js']").data("current-page")) || -1;
  const currentView = $("script[src*='draw_module.js']").data("current-view") || "draw";

  const tooltipTriggerList = $('[title]').toArray();
  tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));

  let page = 0;
  let dataId = 0;
  let label = "";
  let currentSlice = 0;
  let dataJson = null;
  let initialCoordinates = { cz: null, cy: null, cx: null };

  const $drawModal = $("#drawModal");
  const $imgSource = $("#imgDetails-EM");
  const $imgTarget = $("#imgDetails-EM-GT-curve");
  const $imgPreCircle = $("#imgDetails-EM-GT-circlePre");
  const $imgPostCircle = $("#imgDetails-EM-GT-circlePost");

  const updateModalHeader = () => {
    const viewedSlice = $drawModal.data("viewed-instance-slice");
    const middle = dataJson.Middle_Slice;

    // Center badge visibility
    if (viewedSlice === middle) {
      $("#centralBadge").removeClass("d-none");
    } else {
      $("#centralBadge").addClass("d-none");
    }

    // Coordinate display from loaded data
    const { cx0, cy0, _ } = dataJson;
    $("#neuron-id-draw-module").text(`cx: ${parseInt(cx0)} - cy: ${parseInt(cy0)} - cz: ${parseInt(viewedSlice)}`);
  };

  const loadImage = (url, $element) => {
    $.ajax({
      url: url,
      type: "HEAD",
      success: function (data, textStatus, xhr) {
        if (xhr.status === 200) {
          $(new Image())
            .attr("src", url)
            .on("load", function () {
              $element.attr("src", this.src).removeClass("d-none");
            });
        } else if (xhr.status === 204) {
          console.info("Status 204: No content found for image:", url);
          $element.addClass("d-none");
        }
      },
      error: function (xhr) {
        console.error("Error loading image:", url, "Status:", xhr.status);
        $element.addClass("d-none");
      }
    });
  };

  const updateImages = async (dataId, slice) => {
    try {
      await loadImage(`/get_curve_image/${dataId}/${slice}`, $imgTarget);
      if ($imgTarget.hasClass("d-none")) {
        await loadImage(`/get_auto_curve_image/${dataId}/${slice}`, $imgTarget);
      }

      await loadImage(`/get_circle_pre_image/${dataId}/${slice}`, $imgPreCircle);
      await loadImage(`/get_circle_post_image/${dataId}/${slice}`, $imgPostCircle);
    } catch (error) {
      console.error("Error updating images:", error);
    }
  };

  $('[id^="drawButton-"]').click(async function () {
    [page, dataId, label] = $(this).attr("id").replace(/drawButton-/, "").split("-");

    const mode = "draw";
    const load = "full";

    try {
      const reqData = await $.ajax({
        url: "/get_instance",
        type: "POST",
        data: { mode, load, data_id: dataId, page },
      });

      dataJson = JSON.parse(reqData.data);
      currentSlice = dataJson.Middle_Slice;

      $drawModal.data("viewed-instance-slice", currentSlice);

      $imgSource.addClass(label.toLowerCase()).attr(
        "src",
        `/get_source_image/${dataId}/${dataJson.Middle_Slice}`
      );

      if (mode === "draw") {
        await updateImages(dataId, dataJson.Middle_Slice);
      }

      const { cz0, cy0, cx0 } = dataJson;
      const reqNg = await $.ajax({
        url: "/neuro",
        type: "POST",
        data: { cz0, cy0, cx0, mode: "annotate" },
      });

      $("#ng-iframe-draw").attr("src", reqNg.ng_link);

      updateModalHeader();
    } catch (error) {
      console.error("Error loading instance:", error);
    }
  });

  let isModalScrollingLocked = false;
  let modalScrollDelta = 0;
  const MODAL_SCROLL_THRESHOLD = 65;

  $drawModal.on("wheel", async (event) => {
    event.preventDefault();
    if (isModalScrollingLocked) return;

    modalScrollDelta += event.originalEvent.deltaY;

    if (Math.abs(modalScrollDelta) < MODAL_SCROLL_THRESHOLD) return;

    modalScrollDelta = 0;
    isModalScrollingLocked = true;

    $("canvas.curveCanvas, canvas.circleCanvasPre, canvas.circleCanvasPost").addClass("d-none");
    $("#canvasButtonPreCRD, #canvasButtonPostCRD").prop("disabled", false);
    $("#canvasButtonFill, #canvasButtonRevise, #canvasButtonSave").prop("disabled", true);
    $("#canvasButtonDrawMask").prop("disabled", false);
    $("#canvasButtonDrawMask")
      .html('<i class="bi bi-pencil"></i>')
      .attr("title", "Draw Mask");

    const newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

    if (newSlice < dataJson.Min_Slice || newSlice > dataJson.Max_Slice) {
      isModalScrollingLocked = false;
      return;
    }

    try {
      const req = await $.ajax({
        url: "/get_instance",
        type: "POST",
        data: {
          mode: "draw",
          load: "single",
          data_id: dataId,
          page,
          viewedInstanceSlice: newSlice,
        },
      });

      const exists = await $.get(`/source_img_exists/${dataId}/${newSlice}`);
      if (exists) {
        $imgSource.attr("src", `/get_source_image/${dataId}/${newSlice}`);
        await updateImages(dataId, newSlice);
        currentSlice = newSlice;
        $drawModal.data("viewed-instance-slice", newSlice);
        updateModalHeader();
      }
    } catch (error) {
      console.error("Error loading slice:", error);
    } finally {
      isModalScrollingLocked = false;
    }
  });

  $("#add_new_instance").click(async () => {
    try {
      const reqNg = await $.ajax({
        url: "/neuro",
        type: "POST",
        data: { cz0: 0, cy0: 0, cx0: 0, mode: "draw" },
      });

      $("#ng-iframe-draw").attr("src", reqNg.ng_link);
      $("#review_bbox").show();
      $("#back_to_2d").hide();
    } catch (error) {
      console.error("Error adding new instance:", error);
    }
  });

  $("#ng-link-draw").click(() => {
    $("#review_bbox").hide();
    $("#back_to_2d").show();
  });

  $("#back_to_2d").click(() => {
    $("canvas.curveCanvas").removeClass("d-none");
  });

  $("#review_bbox").click(async () => {
    try {
      const data = await $.ajax({
        url: "/ng_bbox_fn",
        type: "POST",
        data: { z1: 0, z2: 0, my: 0, mx: 0 },
      });

      $("#m_x").val(data.mx);
      $("#m_y").val(data.my);
      $("#d_z1").val(data.z1);
      $("#d_z2").val(data.z2);
    } catch (error) {
      console.error("Error reviewing bbox:", error);
    }
  });

  if (currentView === "draw") {
    $("#save_bbox").click(async () => {
      $("#loading-bar").css("display", "flex");

      try {
        await $.ajax({
          url: "/ng_bbox_fn_save",
          type: "POST",
          data: {
            currentPage,
            z1: $("#d_z1").val(),
            z2: $("#d_z2").val(),
            my: $("#m_y").val(),
            mx: $("#m_x").val(),
          },
        });

        $("#drawModalFNSave, #drawModalFN").modal("hide");
        location.reload();
      } catch (error) {
        console.error("Error saving bbox:", error);
      } finally {
        $("#loading-bar").css("display", "none");
      }
    });
  }
});
