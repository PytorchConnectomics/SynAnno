export async function fetchImageExistence(dataId, newSlice, fnPage) {
    try {
      const url = fnPage ? `/source_img_exists/${dataId}/${newSlice}` : `/source_and_target_exist/${dataId}/${newSlice}`;
      return await $.get(url);
    } catch (error) {
      console.error("Image existence check failed:", error);
      return false;
    }
  }

  export async function updateImages(dataId, newSlice, fnPage, $imgSource, $imgTarget) {
    try {
      const newSourceImg = new Image();
      newSourceImg.src = `/get_source_image/${dataId}/${newSlice}`;

      if (fnPage) {
        await new Promise((resolve) => (newSourceImg.onload = resolve));
        $imgSource.attr("src", newSourceImg.src).attr("data-current-slice", newSlice);
      } else {
        const newTargetImg = new Image();
        newTargetImg.src = `/get_target_image/${dataId}/${newSlice}`;

        await Promise.all([
          new Promise((resolve) => (newSourceImg.onload = resolve)),
          new Promise((resolve) => (newTargetImg.onload = resolve)),
        ]);

        $imgSource.attr("src", newSourceImg.src).attr("data-current-slice", newSlice);
        $imgTarget.attr("src", newTargetImg.src).attr("data-current-slice", newSlice);
      }
    } catch (error) {
      console.error("Error updating images:", error);
    }
  }
