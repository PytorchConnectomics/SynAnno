$(document).ready(function () {
    const neuronReady_annotate = $("script[src*='minimap.js']").data("neuron-ready") === true;
    const neuronReady = neuronReady_annotate;

    if (neuronReady) {
        const $minimap = $("#minimapContainer");
        const $header = $("#minimapHeader");
        const $toggleButton = $("#toggleButton");
        const $sharkContainerAnnotate = $("#shark_container_minimap");

        $minimap.show();

        let offsetX, offsetY, isDragging = false;
        let isExpanded = $minimap.data("minimap-state") === "expanded"; // Read initial state

        let prevPosition = {
            top: $minimap.css("top"),
            left: $minimap.css("left"),
            width: $minimap.css("width"),
            height: $minimap.css("height")
        };

        function expandMinimap() {
            const screenWidth = $(window).width();
            const screenHeight = $(window).height();
            $minimap.css({
                width: screenWidth * 0.7 + "px",
                height: screenHeight * 0.7 + "px",
                top: screenHeight * 0.15 + "px",
                left: screenWidth * 0.15 + "px"
            });
            isExpanded = true;
        }

        function collapseMinimap() {
            $minimap.css({
                top: prevPosition.top,
                left: prevPosition.left,
                width: prevPosition.width,
                height: prevPosition.height
            });
            isExpanded = false;
        }

        // Set initial state based on data attribute
        if (isExpanded) {
            expandMinimap();
        }

        // Draggable functionality
        $header.on("mousedown", (e) => {
            isDragging = true;
            offsetX = e.clientX - $minimap.offset().left;
            offsetY = e.clientY - $minimap.offset().top;
            $minimap.css("transition", "none");
        });

        $(document).on("mousemove", (e) => {
            if (isDragging) {
                $minimap.css({
                    left: e.clientX - offsetX + "px",
                    top: e.clientY - offsetY + "px"
                });
            }
        });

        $(document).on("mouseup", () => {
            isDragging = false;
            $minimap.css("transition", "0.2s ease-out");
        });

        // Toggle expansion on button click
        $toggleButton.on("click", function () {
            if (!isExpanded) {
                prevPosition = {
                    top: $minimap.css("top"),
                    left: $minimap.css("left"),
                    width: $minimap.css("width"),
                    height: $minimap.css("height"),
                };
                expandMinimap();
            } else {
                collapseMinimap();
            }

            if (typeof window.setupWindowResizeHandler === "function") {
                setTimeout(() => {
                    window.setupWindowResizeHandler($sharkContainerAnnotate[0]);
                }, 100);
            }
        });
    }
});
