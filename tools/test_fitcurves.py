"""Run with python tools/test_fitcurves.py."""

import math

import numpy as np
from fontTools.pens.basePen import decomposeQuadraticSegment
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from shapely import hausdorff_distance
from shapely.geometry import LineString

if __package__:
    from .fitcurves import draw_fitted, fit_contour
else:
    from fitcurves import draw_fitted, fit_contour


def _samples(segments):
    start = current = np.array(segments[0][1])
    samples = [start[None, :]]
    t = np.linspace(0, 1, 129)[1:, None]
    for kind, coordinates in segments[1:]:
        if kind == "line":
            end = np.array(coordinates)
            samples.append((1 - t) * current + t * end)
            current = end
        else:
            assert kind == "qcurve"
            for control, end in decomposeQuadraticSegment(coordinates):
                control, end = np.array(control), np.array(end)
                samples.append((1 - t)**2 * current + 2 * (1 - t) * t * control + t**2 * end)
                current = end
    if np.any(current != start):
        samples.append((1 - t) * current + t * start)
    return np.vstack(samples)


def _point_count(segments):
    points = [point for kind, data in segments for point in (data if kind == "qcurve" else [data])]
    assert all(type(value) is int for point in points for value in point)
    assert all(a != b for a, b in zip(points, points[1:]))
    return len(points) - (points[0] == points[-1])


def _signed_area(points):
    x, y = np.asarray(points).T
    return 0.5 * (x @ np.roll(y, -1) - y @ np.roll(x, -1))


def test_circle():
    radius = 300
    points = [(radius * math.cos(angle), radius * math.sin(angle))
              for angle in np.linspace(0, math.tau, 400, endpoint=False)]
    segments = fit_contour(points)
    error = np.max(abs(np.linalg.norm(_samples(segments), axis=1) - radius))
    count = _point_count(segments)
    assert error <= 2, error
    assert count <= 24, count
    on_curve = {data[-1] if kind == "qcurve" else data for kind, data in segments}
    assert {(radius, 0), (0, radius), (-radius, 0), (0, -radius)} <= on_curve
    print(f"Circle passed ({error:.3f} units maximum radial deviation, {count} points)")


def test_square():
    size = 800
    steps = range(0, size, 4)
    points = ([(step, 0) for step in steps] + [(size, step) for step in steps]
              + [(size - step, size) for step in steps] + [(0, size - step) for step in steps])
    # Duplicate both an interior vertex and the explicit closing vertex.
    points.insert(23, points[22])
    points += [points[0], points[0]]
    segments = fit_contour(points)
    assert segments == [("move", (0, 0)), ("line", (size, 0)),
                        ("line", (size, size)), ("line", (0, size))], segments
    assert _point_count(segments) == 4
    print("Square passed (4 corners and 4 straight edges)")


def _stroke():
    return LineString([(0, 0), (300, 200), (600, 0)]).buffer(80).exterior


def test_buffered_stroke():
    source = _stroke()
    segments = fit_contour(source.coords)
    error = hausdorff_distance(source, LineString(_samples(segments)), densify=0.125)
    count = _point_count(segments)
    original_count = len(source.coords) - 1
    assert error <= 2, error
    assert 5 * count <= original_count, (count, original_count)
    print(f"Buffered stroke passed ({error:.3f} units Hausdorff distance, "
          f"{original_count} to {count} points, {original_count / count:.2f}x reduction)")


def test_orientation():
    points = list(_stroke().coords)[:-1]
    for order in (points, points[::-1]):
        segments = fit_contour(order)
        source_area = _signed_area(order)
        fitted_area = _signed_area(_samples(segments))
        assert source_area * fitted_area > 0, (source_area, fitted_area)
    print("Orientation passed (clockwise and counterclockwise)")


def test_tt_glyph_pen():
    pen = TTGlyphPen(None)
    stroke = _stroke().coords
    collapsed = [(0, 0.51), (500, 0.51), (500, 0.71), (0, 0.71)]
    assert abs(_signed_area(collapsed)) > 50
    assert fit_contour(collapsed) == []
    # Skip short lists, the area-49.5 triangle, and the collapsed rectangle.
    draw_fitted(pen, [[], [(0, 0), (500, 500)], [(0, 0), (11, 0), (0, 9)], collapsed, stroke])
    glyph = pen.glyph()
    assert glyph.numberOfContours == 1, glyph.numberOfContours
    assert len(glyph.coordinates) == _point_count(fit_contour(stroke))
    assert any(flag & 1 for flag in glyph.flags)
    assert any(flag & 1 == 0 for flag in glyph.flags)
    assert glyph.compile(newTable("glyf"), recalcBBoxes=True)
    print("TTGlyphPen passed (glyph compiled, degenerate contours skipped)")


if __name__ == "__main__":
    test_circle()
    test_square()
    test_buffered_stroke()
    test_orientation()
    test_tt_glyph_pen()
