let currentRequestController = new AbortController();

$(document).ready(() => {
  const currentPage = $("script[src*='annotation.js']").data("current-page");
  // Initial load of the image tiles
  reloadImages(currentPage);
});

$(document).on("shown.bs.modal", "#drawModalFN", () => {
  $("#save_bbox").off("click", handleSaveBboxClick).on("click", handleSaveBboxClick);
});

const handleSaveBboxClick = async () => {
  const currentPage = $("script[src*='annotation.js']").data("current-page");

  // show loading-bar
  $('#loading-bar').css('display', 'flex');

  try {
    // update the bb information with the manual corrections and pass them to the backend
    await $.ajax({
      url: "/ng_bbox_fn_save",
      type: "POST",
      data: {
        currentPage: currentPage,
        z1: $("#d_z1").val(),
        z2: $("#d_z2").val(),
        my: $("#m_y").val(),
        mx: $("#m_x").val(),
      },
    });

    // hide modals
    $("#drawModalFNSave, #drawModalFN").modal("hide");

    // refresh page
    location.reload();
  } catch (error) {
    console.error('Error saving bbox:', error);
  }

  $('#loading-bar').css('display', 'none');

  await reloadImages(currentPage);
};

const reloadImages = async (currentPage) => {
  // Disable the navigation buttons
  toggleNavigationButtons(true);

  // Abort any ongoing request
  currentRequestController.abort();

  // Create a new AbortController for the new request
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
    if (error.name === "AbortError") {
      console.log("Image reload aborted for page:", currentPage);
    } else {
      console.error("Error fetching updated images:", error);
    }
  }
  hideCardGroupLoadingBar();

  // Re-enable the navigation buttons
  toggleNavigationButtons(false);
};

const reloadScripts = (container) => {
  container.find("script").each((_, script) => {
    const newScript = document.createElement("script");

    if (script.type) newScript.type = script.type;
    if (script.src) {
      newScript.src = script.src + "?_=" + new Date().getTime();
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

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

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

// Function to enable/disable navigation buttons
const toggleNavigationButtons = (disable) => {
  if (disable) {
    $("#prev-page").addClass("disabled").find("a").attr("aria-disabled", "true");
    $("#next-page").addClass("disabled").find("a").attr("aria-disabled", "true");
  } else {
    $("#prev-page").removeClass("disabled").find("a").removeAttr("aria-disabled");
    $("#next-page").removeClass("disabled").find("a").removeAttr("aria-disabled");
  }
};
