$(document).ready(function () {

    const canvas = $("canvas.coveringCanvas");
    const ctx = canvas.get(0).getContext("2d");
    ctx.fillStyle = "#FF0000";

    var rect;

    var points = []
    var pointsQBez = []

    // on click activate drawing
    $("#canvasButtonActivate").on("click", function () {
        $("canvas.coveringCanvas").removeClass('d-none')
        rect = $("canvas.coveringCanvas").get(0).getBoundingClientRect() /// get absolute rect. of canvas
        width = canvas.get(0).width
        height = canvas.get(0).height
    });

    // on click activate drawing
    $("#canvasButtonDelete").on("click", function () {
        clear_canvas()
        points = []
    });

    // create mask
    $("#canvasButtonCreate").on("click", function () {
        clear_canvas()
        ctx.beginPath()
        if (points.length > 2) {

            first = true
            for (i = 0; i < points.length - 2; i++) {
                //control.append({x:(points[i+1].x + points[i + 2].x) / 2})

                if (first) {
                    ax = points[i].x
                    ay = points[i].y
                    first = false
                } else {
                    ax = bx
                    ay = by
                }
                bx = (points[i + 1].x + points[i + 2].x) / 2
                by = (points[i + 1].y + points[i + 2].y) / 2
                cx = points[i + 1].x
                cy = points[i + 1].y


                plotQBez(pointsQBez, 100, 10, ax, ay, cx, cy, bx, by)
            }
            plotQBez(pointsQBez, 100, 10, bx, by, points[points.length - 1].x, points[points.length - 1].y, points[points.length - 1].x, points[points.length - 1].y)
            pointsQBez.push({ x: points[points.length - 1].x, y: points[points.length - 1].y })

            let region = new Path2D();

            for (j = 0; j < pointsQBez.length; j++) {
                //ctx.beginPath()
                // the normal aspect ratio of a html5 canvas is 2/1 
                // since we have equal with and equal height, y is distorted by factor 2
                //region.ellipse(pointsQBez[j].x, pointsQBez[j].y, 20, 10, 0, 0, Math.PI * 2)
                region.rect(pointsQBez[j].x-10, pointsQBez[j].y-5, 20, 10);
                //ctx.stroke()

                //region.rect(pointsQBez[j].x-10, pointsQBez[j].y-10,20,20)

            }
            ctx.clip(region)

            ctx.beginPath()

            ctx.fillStyle = "#33FFF0";
            ctx.strokeStyle = "#33FFF0";

            ctx.rect(0, 0, canvas.get(0).width, canvas.get(0).height);
            //draw_quad_line(points, lineWidth = 1, draw_points = false, close_path = true, topOrBot = 'bot')
            ctx.fill()

            ctx.fillStyle = "#FC0EF9";
            ctx.strokeStyle = "#FC0EF9";

            draw_quad_line(points, lineWidth = 1, draw_points = false, close_path = true)
            ctx.fill()



            // draw outer line
            //ctx.strokeStyle = 'rgba(0,0,0,0.7)';
            //ctx.lineCap = 'round'
            //draw_quad_line(points, lineWidth = 20, draw_points = false)

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
    });

    $("canvas.coveringCanvas").on("click", function (e) {
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
    })

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

            intersection_end = intersection(points[pl - 1].x, points[pl - 1].y, points[pl].x, points[pl].y)
            intersection_start = intersection(points[1].x, points[1].y, points[0].x, points[0].y)
            close_intersection(intersection_start, intersection_end)
            ctx.closePath()
        }

        if (!close_path) {
            ctx.stroke();
        }
    }

    function close_intersection(int_start, int_end) {
        // draw line to intersection of the end path with the border
        ctx.lineTo(int_end.x, int_end.y)

        console.log(int_start.d)
        console.log(int_end.d)
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
        }else if (int_start.d == "top" && int_end.d == "left" || int_start.d == "left" && int_end.d == "top") {
            ctx.lineTo(0, 0) // top left corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        }else if (int_start.d == "bot" && int_end.d == "right" || int_start.d == "right" && int_end.d == "bot") {
            ctx.lineTo(width, height) // top right corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        }else if (int_start.d == "bot" && int_end.d == "left" || int_start.d == "left" && int_end.d == "bot") {
            ctx.lineTo(0, height) // top right corner
            ctx.lineTo(int_start.x, int_start.y) // intersection
        }
        // close the path by drawing line to the start point of the path
        ctx.lineTo(points[0].x, points[0].y)

    }

    function intersection(x1, y1, x2, y2) {
        m = slope(x1, x2, y1, y2)
        b = offset(x1, y1, m)

        console.log(x1, y1, x2, y2)
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
        } else if (x2 < x1) {
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

    function plotQBez(pointsQBez, ptCount, pxTolerance, Ax, Ay, Bx, By, Cx, Cy) {
        var deltaBAx = Bx - Ax;
        var deltaCBx = Cx - Bx;
        var deltaBAy = By - Ay;
        var deltaCBy = Cy - By;
        var ax, ay;
        var lastX = -10000;
        var lastY = -10000;
        pointsQBez.push({ x: Ax, y: Ay });
        for (var i = 1; i < ptCount; i++) {
            var t = i / ptCount;
            ax = Ax + deltaBAx * t;
            ay = Ay + deltaBAy * t;
            var x = ax + ((Bx + deltaCBx * t) - ax) * t;
            var y = ay + ((By + deltaCBy * t) - ay) * t;
            var dx = x - lastX;
            var dy = y - lastY;
            if (dx * dx + dy * dy > pxTolerance) {
                pointsQBez.push({ x: x, y: y });
                lastX = x;
                lastY = y;
            }
        }
        pointsQBez.push({ x: Cx, y: Cy });
        return (pointsQBez);
    }
});