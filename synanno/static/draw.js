$(document).ready(function () {

    // retrieve canvas and set 2D context
    const canvas = $("canvas.coveringCanvas");
    const ctx = canvas.get(0).getContext("2d");

    // set red as default color; used for the control points
    ctx.fillStyle = "#FF0000";

    // initialize mouse position to zero
    var mousePosition = {
        x: 0,
        y: 0
    };

    // init default span variables for the canvas
    var width;
    var height;

    // initialize global rectangle variable
    var rect;

    // turn mask drawing and splitting of at the start
    var draw_mask = false;
    var split_mask = false;

    // global buffer for the start, end, and control points of the spline
    var points = []

    // global buffer for the point on the curve
    var pointsQBez = []

    // init thickness
    var thickness = 10

    // define colors
    const turquoise = 'rgba(51, 255, 240)';
    const pink = 'rgba(252, 14, 249)';
    
    // set polarity default
    var color_1 = turquoise
    var color_2 = pink

    // set variable for toggling the polarity
    var color_toggle = 0

    // on click activate canvas
    $("#canvasButtonActivate").on("click", function () {
        // activate canvas for the first time
        if ($("canvas.coveringCanvas").hasClass('d-none')){
            $(this).text("Reset Canvas");
            $("canvas.coveringCanvas").removeClass('d-none') // change visibility
            rect = $("canvas.coveringCanvas").get(0).getBoundingClientRect() // get absolute rect. of canvas
            width = canvas.get(0).width // retrieve the width of the canvas
            height = canvas.get(0).height // retrieve the width of the canvas
            split_mask = false // deactivate mask splitting
            draw_mask = true // activate mask drawing
        // reset canvas
        }else{
            clear_canvas()
            points = []
            pointsQBez = []
            split_mask = false // deactivate mask splitting
            draw_mask = true // activate mask drawing
        }
    });

    // toggle split mode
    var toggle_split = 0

    // activate event for splitting/erasing the curve
    $("#canvasButtonSplit").on("click", function () {
        // activate erasing mode
        if (toggle_split == 0){
            ctx.save()
            ctx.globalCompositeOperation = 'destination-out';
            split_mask = true;
        // deactivate erasing mode
        }else if (toggle_split == 1){
            split_mask = false;
            ctx.restore()
        }
    });

    // if split_mask = true: circular eraser
    $("canvas.coveringCanvas").mousemove(function( event ){
        // set global composite operation to destination-out
        if (split_mask){
            // detect possible changes in mouse position
            if ((mousePosition.x != event.clientX  || mousePosition.y != event.clientY) && event.buttons == 1) {
                mousePosition.x = event.clientX;
                mousePosition.y = event.clientY;

                // Set global composite operation to destination-out
                var pos = getXY(this, event)
                var x = pos.x
                var y = pos.y
                ctx.strokeStyle = "#000";
                ctx.beginPath();
                ctx.moveTo(x + thickness, y)
                ctx.ellipse(x, y, thickness, Math.floor(thickness/2), 0, 0, Math.PI * 2)
                ctx.fill();                    
            }
        }
     })

    // on click activate drawing
    $("#canvasButtonPolarity").on("click", function () {
        if (color_toggle == 0) {
            color_1 = pink
            color_2 = turquoise
            color_toggle = 1
        } else if (color_toggle == 1) {
            color_1 = turquoise
            color_2 = pink
            color_toggle = 0
        }
        fill_clip(color_1, color_2, thickness)
    });

    // create the mask based on the drawn spline
    $("#canvasButtonCreate").on("click", function () {
        draw_mask = false;
        fill_clip(color_1, color_2, thickness)
    });

    // adapt the thickness of the spline
    $('#thickness_range').on('input', function () { 
        thickness = $(this).val()
        fill_clip(color_1, color_2, thickness, sample=false)
    });


    $("canvas.coveringCanvas").on("click", function (e) {
        if (draw_mask){
            clear_canvas()
            ctx.beginPath()
            var pos = getXY(this, e)
            var x = pos.x
            var y = pos.y

            points.push({ x, y })
            if (points.length > 2) {
                draw_quad_line(points)
            }
            else if (points.length > 1) {
                ctx.moveTo((points[0].x), points[0].y);
                ctx.fillRect(points[0].x, points[0].y, 2, 2)
                ctx.fillRect(points[1].x, points[1].y, 2, 2)
                ctx.lineTo(points[0].x, points[0].y);
                ctx.lineTo(points[1].x, points[1].y);
                ctx.stroke();
            }
        }
    })

    function draw_mask(){
        clear_canvas()
            ctx.beginPath()
            var pos = getXY(this, e)
            var x = pos.x
            var y = pos.y

            points.push({ x, y })
            if (points.length > 2) {
                draw_quad_line(points)
            }
            else if (points.length > 1) {
                ctx.moveTo((points[0].x), points[0].y);
                ctx.fillRect(points[0].x, points[0].y, 2, 2)
                ctx.fillRect(points[1].x, points[1].y, 2, 2)
                ctx.lineTo(points[0].x, points[0].y);
                ctx.lineTo(points[1].x, points[1].y);
                ctx.stroke();
            }
    }

    function clear_canvas() {
        ctx.beginPath();
        ctx.clearRect(0, 0, canvas.get(0).width, canvas.get(0).height);
        ctx.stroke();
    }

    function getXY(canvas, evt) {
        // using the absolute rect. of canvas
        return {
            x: (evt.clientX - rect.left) / (rect.right - rect.left) * canvas.width,
            y: (evt.clientY - rect.top) / (rect.bottom - rect.top) * canvas.height
        };
    }

    function fill_clip(color_1, color_2, thickness, sample=true) {
        clear_canvas()
        ctx.beginPath()
        pl = points.length
        if (pl > 2) {

            if (sample){
            ax = points[0].x
            ay = points[0].y
            for (i = 1; i < pl - 2; i++) {
                //control.append({x:(points[i+1].x + points[i + 2].x) / 2})
                
                cx = points[i].x
                cy = points[i].y
                bx = (points[i].x + points[i + 1].x)/2
                by = (points[i].y + points[i + 1].y)/2

                plotQBez(pointsQBez, 100, ax, ay, cx, cy, bx, by)

                ax = bx
                ay = by
            }
            bx = points[pl-1].x
            by = points[pl-1].y
            cx = points[pl-2].x
            cy = points[pl-2].y
            plotQBez(pointsQBez, 100, ax, ay, cx, cy, bx, by)
        }            

            ctx.save();

            let region_1 = new Path2D();
            for (j = 0; j < pointsQBez.length; j++) {
                // the normal aspect ratio of a html5 canvas is 2/1 
                // since we have equal width and height, y is distorted by factor 2
                region_1.moveTo(pointsQBez[j].x + thickness, pointsQBez[j].y)
                region_1.ellipse(pointsQBez[j].x, pointsQBez[j].y, thickness, Math.floor(thickness/2), 0, 0, Math.PI * 2)
            }
            ctx.clip(region_1)

            ctx.fillStyle = color_1;
            ctx.strokeStyle = color_1;

            ctx.rect(0, 0, canvas.get(0).width, canvas.get(0).height);
            ctx.fill()

            ctx.fillStyle = color_2;
            ctx.strokeStyle = color_2
            draw_quad_line(points, lineWidth = 1, draw_points = false, close_path = true)
            ctx.fill()
            ctx.restore();


        }
        else if (points.length > 1) {
            ctx.beginPath()
            ctx.strokeStyle = "#33FFF0"
            ctx.moveTo((points_r[0].x), points_r[0].y);
            ctx.fillRect(points_r[0].x, points_r[0].y, 2, 2)
            ctx.fillRect(points_r[1].x, points_r[1].y, 2, 2)
            ctx.lineTo(points_r[0].x, points_r[0].y);
            ctx.lineTo(points_r[1].x, points_r[1].y);
            ctx.stroke();

            ctx.beginPath()
            ctx.strokeStyle = "#FC0EF9"
            ctx.moveTo((points_l[0].x), points_l[0].y);
            ctx.fillRect(points_l[0].x, points_l[0].y, 2, 2)
            ctx.fillRect(points_l[1].x, points_l[1].y, 2, 2)
            ctx.lineTo(points_l[0].x, points_l[0].y);
            ctx.lineTo(points_l[1].x, points_l[1].y);
            ctx.stroke();
        }
    };

    function draw_quad_line(points, lineWidth = 1, draw_points = true, close_path = false) {
        ctx.beginPath()
        ctx.lineWidth = lineWidth;
        ctx.moveTo((points[0].x), points[0].y);

        if (draw_points) {
            ctx.fillRect(points[0].x, points[0].y, 2, 2)
            if (points.length < 4) {
                ctx.fillRect(points[0].x, points[0].y, 2, 2)
                ctx.fillRect(points[1].x, points[1].y, 2, 2)
            }
            else {
                ctx.fillRect(points[0].x, points[0].y, 2, 2)
            }
        }

        for (i = 1; i < points.length - 2; i++) {
            var xend = (points[i].x + points[i + 1].x) / 2;
            var yend = (points[i].y + points[i + 1].y) / 2;
            ctx.quadraticCurveTo(points[i].x, points[i].y, xend, yend);
            if (draw_points) {
                ctx.fillRect(points[i].x, points[i].y, 2, 2)
                ctx.fillRect(points[i + 1].x, points[i + 1].y, 2, 2)
            }

        }
        // curve through the last two points
        ctx.quadraticCurveTo(points[i].x, points[i].y, points[i + 1].x, points[i + 1].y);
        if (draw_points) {
            ctx.fillRect(points[i + 1].x, points[i + 1].y, 2, 2)
        }

        // close the path with the canvas boundary to clip the path in to two and apply the color
        if (close_path) {
            pl = points.length - 1

            // intersection with it self inside the canvas
            line_intersection = line_intersect(points[pl - 1].x, points[pl - 1].y, points[pl].x, points[pl].y, points[1].x, points[1].y, points[0].x, points[0].y)
            console.log(line_intersection)
            if (!line_intersection){
                console.log("No inter")
                // intersection with boundary
                intersection_end = intersection(points[pl - 1].x, points[pl - 1].y, points[pl].x, points[pl].y)
                intersection_start = intersection(points[1].x, points[1].y, points[0].x, points[0].y)
                close_intersection(intersection_start, intersection_end)
                ctx.closePath()
            }else{
                console.log("intersection")
                ctx.lineTo(line_intersection.x, line_intersection.y)
                ctx.lineTo(points[0].x, points[0].y)
                ctx.closePath()
            }
        }

        if (!close_path) {
            ctx.stroke();
        }
    }

    function close_intersection(int_start, int_end) {
        // draw line to intersection of the end path with the border
        ctx.lineTo(int_end.x, int_end.y)

        if (int_start.d == int_end.d) {
            ctx.lineTo(int_start.x, int_start.y) // if both ends go through the same boarder
        } else if (int_start.d == "bot" && int_end.d == "top") {
            ctx.lineTo(0, 0) // top left corner
            ctx.lineTo(0, height) // bottom left corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "top" && int_end.d == "bot") {
            ctx.lineTo(0, height) // bottom left corner
            ctx.lineTo(0, 0) // top left corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "right" && int_end.d == "left") {
            ctx.lineTo(0, 0) // top left corner
            ctx.lineTo(width, 0) // top right corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "left" && int_end.d == "right") {
            ctx.lineTo(width, 0) // top right corner
            ctx.lineTo(0, 0) // top left corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "top" && int_end.d == "right" || int_start.d == "right" && int_end.d == "top") {
            ctx.lineTo(width, 0) // top right corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "top" && int_end.d == "left" || int_start.d == "left" && int_end.d == "top") {
            ctx.lineTo(0, 0) // top left corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "bot" && int_end.d == "right" || int_start.d == "right" && int_end.d == "bot") {
            ctx.lineTo(width, height) // top right corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        } else if (int_start.d == "bot" && int_end.d == "left" || int_start.d == "left" && int_end.d == "bot") {
            ctx.lineTo(0, height) // top right corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        }
        // close the path by drawing line to the start point of the path
        ctx.lineTo(points[0].x, points[0].y)

    }

    function intersection(x1, y1, x2, y2) {
        m = slope(x1, x2, y1, y2)
        b = offset(x1, y1, m)

        // x1---->x2
        if (x2 > x1) {

            // intersection with the top border 
            if (y2 < y1) {
                x = (0 - b) / m
                if (x <= width && x >= 0) {
                    return { x: x, y: 0, d: "top" }
                }
            }

            // intersection with bottom border
            if (y2 > y1) {
                x = (height - b) / m
                if (x <= width && x >= 0) {
                    return { x: x, y: height, d: "bot" }
                }
            }

            // intersection with the right border
            y = width * m + b
            if (y <= height && y >= 0) {
                return { x: width, y: y, d: "right" }
            }
        } else{
            // intersection with the top border 
            if (y2 < y1) {
                x = (0 - b) / m
                if (x <= width && x >= 0) {
                    return { x: x, y: 0, d: "top" }
                }
            }
            // intersection with bottom border
            if (y2 > y1) {
                x = (height - b) / m
                if (x <= width && x >= 0) {
                    return { x: x, y: height, d: "bot" }
                }
            }
            // intersection with the left border
            y = 0 * m + b
            if (y <= height && y >= 0) {
                return { x: 0, y: y, d: "left" }
            }

        }

    }

    function slope(startX, endX, startY, endY) {
        return (endY - startY) / (endX - startX)
    }

    function offset(x, y, m) {
        return (y - x * m)
    }

    function _getQBezierValue(t, p1, p2, p3) {
        var iT = 1 - t;
        return iT * iT * p1 + 2 * iT * t * p2 + t * t * p3;
    }
    
    function getQuadraticCurvePoint(startX, startY, cpX, cpY, endX, endY, position) {
        return {
            x:  _getQBezierValue(position, startX, cpX, endX),
            y:  _getQBezierValue(position, startY, cpY, endY)
        };
    }

    function plotQBez(pointsQBez, ptCount, Ax, Ay, Cx, Cy, Bx, By) {
        pointsQBez.push({ x: Ax, y: Ay });
        for (var i = 1; i < ptCount; i++) {
            var t = i / ptCount;
            pointsQBez.push(getQuadraticCurvePoint(Ax, Ay, Cx, Cy, Bx, By, t))
        }
        pointsQBez.push({ x: Bx, y: By });
        return (pointsQBez);
    };

    // line intercept math by Paul Bourke http://paulbourke.net/geometry/pointlineplane/
    // Determine the intersection point of two line segments
    // Return FALSE if the lines don't intersect
    function line_intersect(x1, y1, x2, y2, x3, y3, x4, y4) {

        // Check if none of the lines are of length 0
        if ((x1 === x2 && y1 === y2) || (x3 === x4 && y3 === y4)) {
            return false
        }
    
        denominator = ((y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1))
        console.log(denominator)
        // Lines are parallel
        if (denominator === 0) {
            return false
        }
    
        let ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator
        let ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator
    
        // is the intersection along the segments
        if (ua < 0 || ua > 1 || ub < 0 || ub > 1) {
            return false
        }
    
        // Return a object with the x and y coordinates of the intersection
        let x = x1 + ua * (x2 - x1)
        let y = y1 + ua * (y2 - y1)

        // check if intersection is inside boundaries
        if ((x > 0) && (x < width) && ((y > 0) && (y < height))){
            // only return the intersection if it is inside of the curve
            if ((x > x2) && (x > x4)){
                if ((x2 > x1) && (x4 > x3)){
                    return {x:x, y:y}
                }else{
                    return false
                }
            }else if ((x < x2) && (x < x4)){
                if ((x2 < x1) && (x4 < x3)){
                    return {x:x, y:y}
                }else{
                    return false
                }
            }
            return false
        }   
    }

});