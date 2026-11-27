"""Fit dense glyph outlines using Philip J. Schneider's Graphics Gems method."""

import numpy as np
from fontTools.cu2qu.cu2qu import curve_to_quadratic
from fontTools.cu2qu.errors import ApproxNotFoundError
from fontTools.misc.bezierTools import solveQuadratic, splitCubicAtT
from fontTools.pens.areaPen import AreaPen


def _vertices(points):
    points = np.asarray(list(points), dtype=float)
    if len(points) == 0:
        return points
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("contour points must be finite (x, y) pairs")
    keep = np.r_[True, np.any(points[1:] != points[:-1], axis=1)]
    points = points[keep]
    if len(points) > 1 and np.array_equal(points[0], points[-1]):
        points = points[:-1]
    return points


def _cross(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def _area(points):
    local = points - points[0]
    return 0.5 * _cross(local, np.roll(local, -1, axis=0)).sum()


def _unit(vector):
    length = np.linalg.norm(vector)
    return vector / length if length else vector


def _corner_indices(points, lengths, tol, corner_deg):
    stations = np.r_[0.0, np.cumsum(lengths)]
    perimeter = stations[-1]
    stations = stations[:-1]
    width = min(max(1.5 * np.median(lengths), 6 * tol), perimeter / 24)

    def turns(radius):
        before = np.column_stack([
            np.interp(stations - radius, stations, axis, period=perimeter)
            for axis in points.T
        ])
        after = np.column_stack([
            np.interp(stations + radius, stations, axis, period=perimeter)
            for axis in points.T
        ])
        incoming, outgoing = points - before, after - points
        return np.arctan2(abs(_cross(incoming, outgoing)), (incoming * outgoing).sum(axis=1))

    near, far = turns(width), turns(2 * width)
    # A concentrated turn is strong at both scales. A smooth arc's turn
    # grows with the window, and a one-vertex spike fades in the wider scan.
    candidates = np.flatnonzero(
        (near > np.deg2rad(corner_deg)) & (near >= 0.7 * far) & (far >= 0.65 * near)
    )
    taken = np.zeros(len(points), dtype=bool)
    corners = set()
    for index in sorted(candidates, key=lambda i: near[i], reverse=True):
        if not taken[index]:
            corners.add(int(index))
            distance = abs(stations - stations[index])
            taken |= np.minimum(distance, perimeter - distance) < width
    return corners


def _straight_runs(directions, lengths, corners, tol, corner_deg):
    incoming = np.roll(directions, 1, axis=0)
    turns = np.arctan2(abs(_cross(incoming, directions)), (incoming * directions).sum(axis=1))
    ends = sorted(set(np.flatnonzero(turns > 1e-8)) | corners)
    if len(ends) < 2:
        return {}
    spacing = np.median(lengths)
    max_turn = np.deg2rad(min(18, corner_deg))
    runs = {}
    for start, stop in zip(ends, ends[1:] + [ends[0] + len(lengths)]):
        end = stop % len(lengths)
        if ((start not in corners and turns[start] > max_turn)
                or (end not in corners and turns[end] > max_turn)):
            continue
        if stop - start == 1:
            if lengths[start] < max(3 * spacing, 8 * tol):
                continue
        elif np.take(lengths, range(start, stop), mode="wrap").sum() < 4 * tol:
            continue
        runs[start, end] = directions[start]
    starts = {start for start, _ in runs}
    ends = {end for _, end in runs}
    conflicting = (starts & ends) - corners
    return {span: direction for span, direction in runs.items() if conflicting.isdisjoint(span)}


def _end_tangent(points):
    first = points[1] - points[0]
    direction = _unit(first)
    if len(points) < 3:
        return direction
    second = points[2] - points[1]
    next_direction = _unit(second)
    # Extrapolate the secant directions to the endpoint on gently turning data.
    if direction @ next_direction < 0.9:
        return direction
    weight = np.linalg.norm(first) / (np.linalg.norm(first) + np.linalg.norm(second))
    return _unit(direction + weight * (direction - next_direction))


def _straight(points, start_tangent, end_tangent):
    chord = points[-1] - points[0]
    length = np.linalg.norm(chord)
    if not length:
        return False
    direction = chord / length
    if min(direction @ start_tangent, direction @ end_tangent) < 1 - 1e-10:
        return False
    offset = points - points[0]
    return np.all(abs(_cross(offset, direction)) < 1e-7) and np.all(np.diff(offset @ direction) >= 0)


def _generate_cubic(points, parameters, start_tangent, end_tangent):
    """Solve the two least-squares handle lengths for fixed endpoint tangents."""
    t = parameters[:, None]
    s = 1 - t
    b1, b2 = 3 * t * s**2, 3 * t**2 * s
    start, end = points[0], points[-1]
    residual = (points - start) - (b2 + t**3) * (end - start)
    handles = np.column_stack(((b1 * start_tangent).ravel(), (-b2 * end_tangent).ravel()))
    distances, _, rank, _ = np.linalg.lstsq(handles, residual.ravel(), rcond=None)
    chord = np.linalg.norm(end - start)
    if rank < 2 or min(distances) <= max(1e-8, 1e-6 * chord):
        distances = (chord / 3, chord / 3)
    return np.array([start, start + distances[0] * start_tangent,
                     end - distances[1] * end_tangent, end])


def _evaluate(controls, parameters):
    """Evaluate a Bézier curve or one of its derivatives by de Casteljau."""
    t = parameters[:, None, None]
    controls = np.broadcast_to(controls, (len(parameters), *controls.shape))
    while controls.shape[1] > 1:
        controls = (1 - t) * controls[..., :-1, :] + t * controls[..., 1:, :]
    return controls[:, 0, :]


def _measure(cubic, points, parameters, tolerance):
    values = _evaluate(cubic, parameters)
    errors = np.linalg.norm(values - points, axis=1)
    split = 1 + int(np.argmax(errors[1:-1]))
    distance = errors[split]
    if distance > tolerance:
        return distance, split

    left, right = _edge_error_bounds(cubic, points, parameters, values)
    edge = int(np.argmax(np.maximum(left, right)))
    bound = max(left[edge], right[edge])
    if bound > tolerance:
        split = min(max(edge + int(right[edge] > left[edge]), 1), len(points) - 2)
        distance = bound
    return distance, split


def _edge_error_bounds(cubic, points, parameters, values):
    # Compare against the source edges as well as the vertices. On each
    # interval the curve minus its matched linear edge is itself a cubic,
    # so its control vectors bound the distance in both directions.
    delta = values - points
    tangents = _evaluate(3 * np.diff(cubic, axis=0), parameters)
    step = np.diff(parameters)[:, None] / 3
    edge_step = np.diff(points, axis=0) / 3
    left = delta[:-1] + step * tangents[:-1] - edge_step
    right = delta[1:] - step * tangents[1:] + edge_step
    return np.linalg.norm(left, axis=1), np.linalg.norm(right, axis=1)


def _reparameterize(cubic, points, parameters):
    residual = _evaluate(cubic, parameters) - points
    derivative = 3 * np.diff(cubic, axis=0)
    velocity = _evaluate(derivative, parameters)
    acceleration = _evaluate(2 * np.diff(derivative, axis=0), parameters)
    denominator = (velocity**2 + residual * acceleration).sum(axis=1)
    correction = np.divide((residual * velocity).sum(axis=1), denominator,
                           out=np.zeros_like(parameters), where=denominator > 0)
    adjusted = parameters - correction
    adjusted[0], adjusted[-1] = 0, 1
    return adjusted


def _fit_run(points, tangents, start_tangent, end_tangent, tolerance):
    """Yield straight endpoints or cubics in order, sharing tangents at splits."""
    pending = [(0, len(points) - 1, start_tangent, end_tangent)]
    while pending:
        start, end, left, right = pending.pop()
        run = points[start:end + 1]
        if _straight(run, left, right):
            yield run[-1]
            continue
        if len(run) == 2:
            step = (run[1] - run[0]) / 3
            length = np.linalg.norm(step)
            mismatch = max(np.linalg.norm(left * length - step),
                           np.linalg.norm(right * length - step))
            # Short handles stay close to the chord with controls at its
            # endpoints, while still retaining the tangent directions.
            if mismatch > tolerance:
                length = min(length, tolerance / 2)
            yield np.array([run[0], run[0] + left * length,
                            run[1] - right * length, run[1]])
            continue

        stations = np.r_[0.0, np.linalg.norm(np.diff(run, axis=0), axis=1).cumsum()]
        parameters = stations / stations[-1]
        best_error = np.inf
        for _ in range(8):
            cubic = _generate_cubic(run, parameters, left, right)
            error, split = _measure(cubic, run, parameters, tolerance)
            if error <= tolerance:
                yield cubic
                break
            if error >= best_error:
                break
            best_error, best_split = error, split
            parameters = _reparameterize(cubic, run, parameters)
            if not np.all(np.diff(parameters) > 0):
                break
        if error > tolerance:
            middle = start + best_split
            tangent = tangents[middle]
            pending.append((middle, end, tangent, right))
            pending.append((start, middle, left, tangent))


def _quadratic_splines(cubic, max_error):
    # Split where either coordinate derivative vanishes to make extrema explicit.
    p0, p1, p2, p3 = cubic
    edge0, edge1, edge2 = p1 - p0, p2 - p1, p3 - p2
    roots = set()
    for a, b, c in zip(edge0 - 2 * edge1 + edge2, 2 * (edge1 - edge0), edge0):
        scale = max(abs(a), abs(b), abs(c))
        if scale:
            roots.update(t for t in solveQuadratic(a / scale, b / scale, c / scale)
                         if 1e-7 < t < 1 - 1e-7)
    pieces = splitCubicAtT(*map(tuple, cubic), *sorted(roots))
    pending = list(reversed(pieces))
    while pending:
        piece = pending.pop()
        try:
            yield curve_to_quadratic(piece, max_error)
        except ApproxNotFoundError:
            left, right = splitCubicAtT(*piece, 0.5)
            pending.extend((right, left))


def _spline_tracks_polyline(spline, points, stations, stops, positions, tolerance):
    controls = spline[1:-1]
    knots = np.vstack((spline[0], (controls[:-1] + controls[1:]) / 2, spline[-1]))
    for index, (start, end, control) in enumerate(zip(knots, knots[1:], controls)):
        left, right = stops[index:index + 2]
        interior = (stations > left) & (stations < right)
        source = np.vstack((positions[index], points[interior], positions[index + 1]))
        parameters = (np.r_[left, stations[interior], right] - left) / (right - left)
        cubic = np.array([start, start + (2 / 3) * (control - start),
                          end + (2 / 3) * (control - end), end])
        for _ in range(3):
            updated = _reparameterize(cubic, source, parameters)
            if not np.all(np.diff(updated) > 0):
                break
            parameters = updated
        values = _evaluate(cubic, parameters)
        if np.max(np.linalg.norm(values - source, axis=1)) > tolerance:
            return False
        if np.max(_edge_error_bounds(cubic, source, parameters, values)) > tolerance:
            return False
    return True


def _compact_spline(points, tangents, max_controls, tolerance):
    """Try a shorter implied-knot spline for a smooth run between two lines."""
    stations = np.r_[0.0, np.linalg.norm(np.diff(points, axis=0), axis=1).cumsum()]
    for count in range(2, max_controls + 1):
        stops = np.linspace(0, stations[-1], count + 1)
        positions = np.column_stack([np.interp(stops, stations, axis) for axis in points.T])
        directions = np.column_stack([np.interp(stops, stations, axis) for axis in tangents.T])
        left, right = directions[:-1], directions[1:]
        chords = np.diff(positions, axis=0)
        determinant = _cross(left, right)
        if np.any(abs(determinant) < 1e-8):
            continue
        forward = _cross(chords, right) / determinant
        backward = _cross(left, chords) / determinant
        if min(np.min(forward), np.min(backward)) <= 0:
            continue
        # For near-circular runs, nearby tangent intersections already lie
        # on either side of the intended joins. Check the actual rounded
        # spline, with TrueType's implicit midpoints, against the polyline.
        controls = positions[:-1] + forward[:, None] * left
        spline = np.rint(np.vstack((points[0], controls, points[-1])))
        if (np.all(np.any(np.diff(spline, axis=0), axis=1))
                and _spline_tracks_polyline(spline, points, stations, stops, positions, tolerance)):
            return spline
    return None


def _rounded(point):
    return int(round(point[0])), int(round(point[1]))


def _append_line(segments, point):
    if point != _endpoint(segments[-1]):
        segments.append(("line", point))


def _endpoint(segment):
    kind, coordinates = segment
    return coordinates[-1] if kind == "qcurve" else coordinates


def _append_spline(segments, spline):
    rounded = list(map(_rounded, spline))
    rounded[0] = _endpoint(segments[-1])
    if (rounded[0] != rounded[-1]
            and all(a != b for a, b in zip(rounded, rounded[1:]))):
        segments.append(("qcurve", rounded[1:]))
        return

    # Expand implied knots only when quantization collapses consecutive points.
    # Dropping a repeated control directly would move its adjacent quadratics.
    controls = rounded[1:-1]
    end = rounded[-1]
    for control, next_control in zip(controls, controls[1:] + [None]):
        knot = end if next_control is None else _rounded((np.array(control) + next_control) / 2)
        start = _endpoint(segments[-1])
        if start != knot:
            if control in (start, knot):
                _append_line(segments, knot)
            else:
                segments.append(("qcurve", [control, knot]))


def _fit(points, tol, corner_deg):
    edges = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(edges, axis=1)
    directions = edges / lengths[:, None]
    corners = _corner_indices(points, lengths, tol, corner_deg)
    lines = _straight_runs(directions, lengths, corners, tol, corner_deg)
    # Interpolate the unit secants at the vertex, weighting by their distances
    # from it. Both adjacent runs use this same direction at a smooth knot.
    previous = np.roll(lengths, 1)
    mixed = np.roll(directions, 1, axis=0) * lengths[:, None] + directions * previous[:, None]
    tangents = np.array([_unit(vector) for vector in mixed])
    tangents[~np.any(tangents, axis=1)] = directions[~np.any(tangents, axis=1)]
    for (start, end), direction in lines.items():
        tangents[start] = tangents[end] = direction

    line_anchors = {index for line in lines for index in line}
    smooth_line_anchors = line_anchors - corners
    anchors = corners | line_anchors
    if corners:
        start = min(corners)
    else:
        axis = int(np.argmax(np.ptp(points, axis=0)))
        start = int(np.argmax(points[:, axis]))
        # An extremum can lie anywhere along a flat edge. Keep its existing
        # endpoint so starting there does not divide one straight run in two.
        if start not in anchors:
            for first, last in lines:
                if ((start - first) % len(points) < (last - first) % len(points)
                        and points[first, axis] == points[start, axis]):
                    start = first
                    break
    anchors.add(start)
    if len(anchors) == 1:
        extrema = set(np.r_[points.argmin(axis=0), points.argmax(axis=0)])
        stations = np.r_[0.0, lengths.cumsum()]
        intervals = np.diff(stations[sorted(extrema)], append=stations[min(extrema)] + stations[-1])
        if len(extrema) == 4 and min(intervals) > stations[-1] / 8:
            anchors.update(extrema)
        else:
            anchors.add(int(np.argmax(np.linalg.norm(points - points[start], axis=1))))

    count = len(points)
    stops = sorted(start + (index - start) % count for index in anchors)
    segments = [("move", _rounded(points[start]))]
    for first, last in zip(stops, stops[1:] + [start + count]):
        begin, end = first % count, last % count
        if (begin, end) in lines:
            _append_line(segments, _rounded(points[end]))
            continue
        indices = np.arange(first, last + 1) % count
        run = points[indices]
        left = _end_tangent(run) if begin in corners else tangents[begin]
        right = -_end_tangent(run[::-1]) if end in corners else tangents[end]
        # Reserve part of the error budget for conversion and grid rounding.
        pieces = []
        for piece in _fit_run(run, tangents[indices], left, right, tol * 0.65):
            if piece.ndim == 1:
                pieces.append(piece)
            else:
                pieces.extend(np.asarray(spline) for spline in _quadratic_splines(piece, tol * 0.5))

        if begin in smooth_line_anchors and end in smooth_line_anchors:
            # Keep explicit extrema unless an implied spline saves several points.
            max_controls = min(4, sum(len(piece) - 1 for piece in pieces) - 4)
            if max_controls >= 2:
                compact = _compact_spline(run, tangents[indices], max_controls, tol)
                if compact is not None:
                    pieces = [compact]
        for piece in pieces:
            if piece.ndim == 1:
                _append_line(segments, _rounded(piece))
            else:
                _append_spline(segments, piece)
    if segments[-1] == ("line", segments[0][1]):
        segments.pop()
    return segments if len(segments) > 1 else []


def _validate_options(tol, corner_deg):
    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    if not 0 <= corner_deg <= 180:
        raise ValueError("corner_deg must be between 0 and 180")


def _draw_segments(pen, segments):
    if not segments:
        return
    pen.moveTo(segments[0][1])
    for kind, coordinates in segments[1:]:
        if kind == "line":
            pen.lineTo(coordinates)
        else:
            pen.qCurveTo(*coordinates)
    pen.closePath()


def _fit_with_winding(points, area, tol, corner_deg):
    segments = _fit(points, tol, corner_deg)
    pen = AreaPen()
    _draw_segments(pen, segments)
    if pen.value * area > 0:
        return segments

    # A narrow region can collapse during fitting or grid rounding. If the
    # rounded polygon still has the original winding, retain its own edges.
    segments = [("move", _rounded(points[0]))]
    for point in points[1:]:
        _append_line(segments, _rounded(point))
    if segments[-1] == ("line", segments[0][1]):
        segments.pop()
    pen = AreaPen()
    _draw_segments(pen, segments)
    return segments if pen.value * area > 0 else []


def fit_contour(points, tol=1.5, corner_deg=35.0):
    """Fit a closed polygon whose last vertex may repeat its first vertex.

    Return a move, then lines and TrueType quadratic splines. Coordinates are
    integers. The last point of each spline is on-curve, with implied knots
    between consecutive off-curve points. The contour keeps its input winding
    and its final straight edge, if any, is implicit. An outline that
    collapses on the integer grid returns an empty list.
    """
    _validate_options(tol, corner_deg)
    points = _vertices(points)
    if len(points) < 3:
        return []
    area = _area(points)
    return _fit_with_winding(points, area, tol, corner_deg) if area else []


def draw_fitted(pen, polygons, tol=1.5, corner_deg=35.0):
    """Draw into a segment pen, skipping contours under 3 vertices or 50 units²."""
    _validate_options(tol, corner_deg)
    for polygon in polygons:
        points = _vertices(polygon)
        if len(points) < 3:
            continue
        area = _area(points)
        if abs(area) >= 50:
            _draw_segments(pen, _fit_with_winding(points, area, tol, corner_deg))
