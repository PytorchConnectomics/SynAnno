export function updateLabelClasses(dataId, label) {
    const labelMappings = {
      unsure: { remove: "unsure", add: "correct", newLabel: "correct" },
      incorrect: { remove: "incorrect", add: "unsure", newLabel: "unsure" },
      correct: { remove: "correct", add: "incorrect", newLabel: "incorrect" },
    };

    if (labelMappings[label]) {
      const { remove, add, newLabel } = labelMappings[label];
      $(`#id${dataId}`).removeClass(remove).addClass(add);
      $(`#id-a-${dataId}`).attr("label", newLabel);
    }
  }
