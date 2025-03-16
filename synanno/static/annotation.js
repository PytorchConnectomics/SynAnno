let currentRequestController = new AbortController();

$(document).ready(() => {
  const currentPage = $("script[src*='annotation.js']").data("current-page");
  reloadImages(currentPage);
});

$(document).on("shown.bs.modal", "#drawModalFN", () => {
  $("#save_bbox").off("click").on("click", handleSaveBboxClick);
});

const handleSaveBboxClick = async () => {
  const currentPage = $("script[src*='annotation.js']").data("current-page");
  $('#loading-bar').css('display', 'flex');

  $(".text-white").text("Saving new instance...");

  try {
    await $.post("/ng_bbox_fn_save", {
      currentPage,
      z1: $("#d_z1").val(),
      z2: $("#d_z2").val(),
      my: $("#m_y").val(),
      mx: $("#m_x").val()
    });

    $("#drawModalFNSave, #drawModalFN").modal("hide");
    location.reload();
  } catch (error) {
    console.error("Error saving bbox:", error);
  }
  $('#loading-bar').css('display', 'none');
};

const reloadImages = async (currentPage) => {
  toggleNavigationButtons(true);
  currentRequestController.abort();
  currentRequestController = new AbortController();
  const { signal } = currentRequestController;

  showCardGroupLoadingBar();

  try {
    const response = await fetch(`/update_image_tiles/${currentPage}`, { signal });
    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

    const html = await response.text();
    const container = $("<div>").html(html);

    $("#card-group-container").html(container.html());
    reloadScripts(container);
  } catch (error) {
    if (error.name !== "AbortError") {
      console.error("Error fetching updated images:", error);
    }
  }

  hideCardGroupLoadingBar();
  toggleNavigationButtons(false);
};

const reloadScripts = (container) => {
  container.find("script").each((_, script) => {
    const newScript = document.createElement("script");
    if (script.type) newScript.type = script.type;
    if (script.src) {
      newScript.src = `${script.src}?_=${new Date().getTime()}`;
      newScript.async = false;
      const existingScript = document.querySelector(`script[src^="${script.src}"]`);
      if (existingScript) existingScript.remove();
      document.body.appendChild(newScript);
    } else {
      newScript.textContent = script.textContent;
      document.body.appendChild(newScript);
      document.body.removeChild(newScript);
    }
  });
};

const showCardGroupLoadingBar = async () => {
  try {
    const response = await fetch(`/loading_bar_image_tiles`);
    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

    const html = await response.text();
    const container = $("<div>").html(html);
    await $(".card-group").html(container.html());
  } catch (error) {
    console.error("Error fetching loading bar:", error);
  }

  $("#loading-bar-card-group").css("display", "flex");
};

const hideCardGroupLoadingBar = () => {
  $("#loading-bar-card-group").css("display", "none");
};

const toggleNavigationButtons = (disable) => {
  $("#prev-page, #next-page").toggleClass("disabled", disable)
    .find("a").attr("aria-disabled", disable ? "true" : null);
};
