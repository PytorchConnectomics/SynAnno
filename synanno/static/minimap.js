$(document).ready(function () {
    const neuronReady = $("script[src*='minimap.js']").data("neuron-ready") === true;
    const $minimap = $("#minimapContainer");
    const $header = $("#minimapHeader");
    const $toggleButton = $("#toggleButton");
    const $sharkContainerAnnotate = $("#shark_container_minimap");
    const $content = $(".container");

    if (neuronReady) {
        $minimap.css("display", "flex");
    }

    let offsetX, offsetY, isDragging = false;
    let dragThreshold = 5; // Minimum movement to count as drag
    let wasDragged = false; // Prevents accidental toggling
    let isExpanded = $minimap.data("minimap-state") === "expanded";

    let prevPosition = {
        top: $minimap.css("top"),
        left: $minimap.css("left"),
        width: $minimap.css("width"),
        height: $minimap.css("height")
    };

    function expandMinimap() {
        const screenWidth = $(window).width();
        const screenHeight = $(window).height();

        // Move minimap **outside** the flex container if needed
        if ($minimap.parent().is(".d-flex")) {
            $minimap.detach().appendTo("body");
        }

        $minimap.addClass("expanded").css({
            position: "fixed",
            width: "70vw",
            height: "70vh",
            top: "15vh",
            left: "15vw",
            zIndex: 1001
        });

        isExpanded = true;
        $minimap.data("minimap-state", "expanded");
    }

    function collapseMinimap() {
        $minimap.removeClass("expanded").css({
            position: "relative",
            top: "auto",
            left: "auto",
            width: prevPosition.width,
            height: prevPosition.height
        });

        // Move minimap **back inside** the flex container
        $(".flex-container").prepend($minimap);

        isExpanded = false;
        $minimap.data("minimap-state", "collapsed");
    }

    if (isExpanded) {
        expandMinimap();
    }

    // Draggable functionality (only when expanded)
    $header.on("mousedown", (e) => {
        if (!isExpanded) return; // Disable dragging when minimap is collapsed

        isDragging = true;
        wasDragged = false;
        offsetX = e.clientX - $minimap.offset().left;
        offsetY = e.clientY - $minimap.offset().top;
        $minimap.css("transition", "none");
    });

    $(document).on("mousemove", (e) => {
        if (!isDragging || !isExpanded) return; // Disable dragging when minimap is collapsed

        let moveX = Math.abs(e.clientX - offsetX - $minimap.offset().left);
        let moveY = Math.abs(e.clientY - offsetY - $minimap.offset().top);

        if (moveX > dragThreshold || moveY > dragThreshold) {
            wasDragged = true; // Detect dragging motion
        }

        $minimap.css({
            left: e.clientX - offsetX + "px",
            top: e.clientY - offsetY + "px"
        });
    });

    $(document).on("mouseup", () => {
        isDragging = false;
        $minimap.css("transition", "0.2s ease-out");
    });

    // Toggle expansion on button click
    $toggleButton.on("click", function () {
        if (wasDragged) {
            // Ignore click if the minimap was just dragged
            wasDragged = false;
            return;
        }

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
});
