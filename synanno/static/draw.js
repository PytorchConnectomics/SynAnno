$(document).ready(function () {

    const canvas = $("canvas.coveringCanvas");
    const ctx = canvas.get(0).getContext("2d");
    ctx.fillStyle = "#FF0000";

    var points = []
    var vectors = []

// variables defining a cubic bezier curve
var PI2 = Math.PI * 2;
var s = {
    x: 20,
    y: 30
};
var c1 = {
    x: 200,
    y: 40
};
var c2 = {
    x: 40,
    y: 200
};
var e = {
    x: 270,
    y: 220
};

// an array of points plotted along the bezier curve
var points = [];

// we use PI often so put it in a variable
var PI = Math.PI;

// plot 400 points along the curve
// and also calculate the angle of the curve at that point
for (var t = 0; t <= 100; t += 0.25) {

    var T = t / 100;

    // plot a point on the curve
    var pos = getQuadraticCurvePoint(s, c1, c2, e, T);

    // calculate the tangent angle of the curve at that point
    var tx = bezierTangent(s.x, c1.x, c2.x, e.x, T);
    var ty = bezierTangent(s.y, c1.y, c2.y, e.y, T);
    var a = Math.atan2(ty, tx) - PI / 2;

    // save the x/y position of the point and the tangent angle
    // in the points array
    points.push({
        x: pos.x,
        y: pos.y,
        angle: a
    });
}

console.log(points)
// Note: increase the lineWidth if 
// the gradient has noticable gaps 
ctx.lineWidth = 2;

// draw a gradient-stroked line tangent to each point on the curve
for (var i = 0; i < points.length; i++) {

    // calc the topside and bottomside points of the tangent line
    var offX1 = points[i].x + 20 * Math.cos(points[i].angle);
    var offY1 = points[i].y + 20 * Math.sin(points[i].angle);
    var offX2 = points[i].x + 20 * Math.cos(points[i].angle - PI);
    var offY2 = points[i].y + 20 * Math.sin(points[i].angle - PI);

    // create a gradient stretching between 
    // the calculated top & bottom points
    var gradient = ctx.createLinearGradient(offX1, offY1, offX2, offY2);
    gradient.addColorStop(0.00, 'red');
    gradient.addColorStop(1 / 6, 'orange');
    gradient.addColorStop(2 / 6, 'yellow');
    gradient.addColorStop(3 / 6, 'green')
    gradient.addColorStop(4 / 6, 'aqua');
    gradient.addColorStop(5 / 6, 'blue');
    gradient.addColorStop(1.00, 'purple');

    // draw the gradient-stroked line at this point
    ctx.strokeStyle = gradient;
    ctx.beginPath();
    ctx.moveTo(offX1, offY1);
    ctx.lineTo(offX2, offY2);
    ctx.stroke();
}


// draw a top stroke to cover jaggies
// on the top of the gradient curve
var offX1 = points[0].x + 20 * Math.cos(points[0].angle);
var offY1 = points[0].y + 20 * Math.sin(points[0].angle);
ctx.strokeStyle = "red";
// Note: increase the lineWidth if this outside of the
//       gradient still has jaggies
ctx.lineWidth = 1.5;
ctx.beginPath();
ctx.moveTo(offX1, offY1);
for (var i = 1; i < points.length; i++) {
    var offX1 = points[i].x + 20 * Math.cos(points[i].angle);
    var offY1 = points[i].y + 20 * Math.sin(points[i].angle);
    ctx.lineTo(offX1, offY1);
}
ctx.stroke();


// draw a bottom stroke to cover jaggies
// on the bottom of the gradient
var offX2 = points[0].x + 20 * Math.cos(points[0].angle + PI);
var offY2 = points[0].y + 20 * Math.sin(points[0].angle + PI);
ctx.strokeStyle = "purple";
// Note: increase the lineWidth if this outside of the
//       gradient still has jaggies
ctx.lineWidth = 1.5;
ctx.beginPath();
ctx.moveTo(offX2, offY2);
for (var i = 0; i < points.length; i++) {
    var offX2 = points[i].x + 20 * Math.cos(points[i].angle + PI);
    var offY2 = points[i].y + 20 * Math.sin(points[i].angle + PI);
    ctx.lineTo(offX2, offY2);
}
ctx.stroke();


//////////////////////////////////////////
// helper functions
//////////////////////////////////////////

// calculate one XY point along Cubic Bezier at interval T
// (where T==0.00 at the start of the curve and T==1.00 at the end)
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

// calculate the tangent angle at interval T on the curve
function bezierTangent(a, b, c, d, t) {
    return (3 * t * t * (-a + 3 * b - 3 * c + d) + 6 * t * (a - 2 * b + c) + 3 * (-a + b));
};

});