import Foundation

/// Maps between seconds and fractional bar index.
///
/// Every tab plots against bars rather than wall-clock seconds, so the picture
/// is musical: even spacing on screen means even musical time. Apple's grid
/// tracks the performance rather than laying a fixed ruler over it, so this
/// reads the actual downbeat times instead of dividing by a tempo.
struct BarGrid {
    private let times: [Double]
    private let indices: [Double]

    init(bars: [Bar]) {
        let ordered = bars.sorted { $0.t < $1.t }
        times = ordered.map(\.t)
        indices = ordered.map { Double($0.idx) }
    }

    var firstBar: Double { indices.first ?? 0 }

    var lastBar: Double { indices.last ?? 0 }

    /// Seconds per bar at the end of the track, used to extrapolate past the
    /// final downbeat. NOT because a scored loop window can reach past it —
    /// `LoopScorer.score` only ever emits windows ending at an existing bar
    /// index (it iterates `0..<(ordered.count - nBars)`). The real reason:
    /// instrument-activity samples run to the track's actual duration, which
    /// is typically later than the beat tracker's last detected downbeat (an
    /// outro fades out after tracking gives up), so plotting them needs a bar
    /// position beyond the last known one.
    private var tailGap: Double {
        guard times.count > 1 else { return 2.0 }
        return times[times.count - 1] - times[times.count - 2]
    }

    func barAt(_ t: Double) -> Double {
        guard !times.isEmpty else { return 0 }
        guard times.count > 1 else { return indices[0] }
        if t <= times[0] {
            return indices[0] + (t - times[0]) / (times[1] - times[0])
        }
        if t >= times[times.count - 1] {
            return indices[indices.count - 1]
                + (t - times[times.count - 1]) / tailGap
        }
        var lo = 0, hi = times.count - 1
        while hi - lo > 1 {
            let mid = (lo + hi) / 2
            if times[mid] <= t { lo = mid } else { hi = mid }
        }
        return indices[lo]
            + (t - times[lo]) / (times[hi] - times[lo]) * (indices[hi] - indices[lo])
    }

    func time(atBar bar: Double) -> Double {
        guard !times.isEmpty else { return 0 }
        guard times.count > 1 else { return times[0] }
        if bar <= indices[0] {
            return times[0] + (bar - indices[0]) * (times[1] - times[0])
        }
        if bar >= indices[indices.count - 1] {
            return times[times.count - 1]
                + (bar - indices[indices.count - 1]) * tailGap
        }
        var lo = 0, hi = indices.count - 1
        while hi - lo > 1 {
            let mid = (lo + hi) / 2
            if indices[mid] <= bar { lo = mid } else { hi = mid }
        }
        return times[lo]
            + (bar - indices[lo]) * (times[hi] - times[lo]) / (indices[hi] - indices[lo])
    }
}
