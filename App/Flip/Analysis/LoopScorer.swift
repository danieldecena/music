import Foundation

struct Bar: Equatable {
    let idx: Int
    let t: Double
}

struct TrackSection: Equatable {
    let start: Double
    let end: Double
}

struct ActivitySample: Equatable {
    let instrument: String
    let start: Double
    let end: Double
    let level: Double
}

struct LoopCandidate: Identifiable, Equatable {
    let startBar: Int
    let start: Double
    let end: Double
    let nBars: Int
    let score: Double
    let instruments: [String: Double]
    var id: Int { startBar }
}

/// Port of `Scripts/regions.py:score_loops`. The phone and the Mac must agree
/// about which loop is best, so any change here needs the same change there and
/// the parity test re-run.
enum LoopScorer {
    /// A window that no section contains is worth less: it crosses a musical
    /// seam, so it will not loop cleanly.
    static let straddlePenalty = 0.75
    /// The instrument whose absence defines a clean loop.
    static let cleanOf = "vocal"

    /// Duration-weighted mean level per instrument over [start, end).
    ///
    /// Weighted rather than a plain average because the samples are intervals:
    /// an unweighted mean lets a run of short samples outvote one long sample
    /// covering most of the span.
    static func meanLevels(_ activity: [ActivitySample],
                           _ start: Double, _ end: Double) -> [String: Double] {
        var num: [String: Double] = [:]
        var den: [String: Double] = [:]
        for a in activity {
            let lo = max(a.start, start)
            let hi = min(a.end, end)
            var w = hi - lo
            if w <= 0 {
                // A zero-length sample still carries a reading. Give it minimal
                // weight rather than dropping it, or a sparse signal scores as
                // absent when it is merely sparse.
                guard a.start >= start && a.start < end else { continue }
                w = 1e-9
            }
            num[a.instrument, default: 0] += a.level * w
            den[a.instrument, default: 0] += w
        }
        return num.reduce(into: [:]) { out, kv in
            if let d = den[kv.key], d > 0 { out[kv.key] = kv.value / d }
        }
    }

    static func contained(_ sections: [TrackSection],
                          _ start: Double, _ end: Double) -> Bool {
        sections.contains { $0.start <= start && end <= $0.end }
    }

    static func score(bars: [Bar], sections: [TrackSection],
                      activity: [ActivitySample], nBars: Int) -> [LoopCandidate] {
        let ordered = bars.sorted { $0.t < $1.t }
        guard ordered.count > nBars else { return [] }

        return (0..<(ordered.count - nBars)).map { i in
            let start = ordered[i].t
            let end = ordered[i + nBars].t
            let levels = meanLevels(activity, start, end)
            let clean = 1.0 - (levels[cleanOf] ?? 0.0)
            let mult = contained(sections, start, end) ? 1.0 : straddlePenalty
            return LoopCandidate(startBar: ordered[i].idx, start: start, end: end,
                                 nBars: nBars, score: clean * mult,
                                 instruments: levels)
        }
    }
}
