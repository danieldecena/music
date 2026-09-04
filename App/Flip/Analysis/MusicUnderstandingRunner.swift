import AVFoundation
import Foundation
import MusicUnderstanding

/// What one analysis produced, flattened for display.
struct Summary: Sendable, Equatable {
    var bpm: Double = 0
    var beats = 0
    var bars = 0
    var sections = 0
    var segments = 0
    var phrases = 0
    var key = "-"
    var instruments: [String] = []
    var elapsed: TimeInterval = 0
    var jsonBytes = 0
    var jsonData = Data()
    var duration: TimeInterval = 0
}

enum Runner {
    /// Runs all six analyses and flattens the result.
    ///
    /// Reads the fields back out of the encoded JSON rather than off the Swift
    /// types. `SessionResult` is `Encodable`, the JSON shape is already verified
    /// against the macOS tool (`Tools/mu-analyze.swift`), and going through it
    /// keeps this file and that one reading the same thing by construction.
    static func analyze(url: URL) async throws -> Summary {
        let asset = AVURLAsset(url: url)
        let duration = try await asset.load(.duration).seconds
        let session = try await MusicUnderstandingSession(asset: asset)

        let started = Date()
        let result = try await session.analyze(for: [
            .rhythm, .key, .structure, .loudness, .pace, .instrumentActivity,
        ])
        let elapsed = Date().timeIntervalSince(started)

        let encoder = JSONEncoder()
        // Loudness reports -inf LUFS for digital silence and JSONEncoder throws
        // on non-finite floats, discarding an analysis that already succeeded.
        encoder.nonConformingFloatEncodingStrategy = .convertToString(
            positiveInfinity: "inf", negativeInfinity: "-inf", nan: "nan")
        let data = try encoder.encode(result)
        let obj = (try JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]

        var s = Summary()
        s.elapsed = elapsed
        s.jsonBytes = data.count
        s.jsonData = data
        s.duration = duration

        if let r = obj["rhythm"] as? [String: Any] {
            s.bpm = r["beatsPerMinute"] as? Double ?? 0
            s.beats = (r["beats"] as? [Any])?.count ?? 0
            s.bars = (r["bars"] as? [Any])?.count ?? 0
        }
        if let st = obj["structure"] as? [String: Any] {
            s.sections = (st["sections"] as? [Any])?.count ?? 0
            s.segments = (st["segments"] as? [Any])?.count ?? 0
            s.phrases = (st["phrases"] as? [Any])?.count ?? 0
        }
        if let k = obj["key"] as? [String: Any],
           let ranges = k["ranges"] as? [[String: Any]],
           let value = ranges.first?["value"] as? [String: Any] {
            s.key = "\(value["tonic"] ?? "?") \(value["mode"] ?? "?")"
        }
        if let ia = obj["instrumentActivity"] as? [String: Any],
           let activity = ia["activity"] as? [String: Any] {
            s.instruments = activity.keys.sorted()
        }
        return s
    }

    /// The full analysis, not just the counts. Reads fields back out of the
    /// encoded JSON for the same reason `analyze(url:)` does: the JSON shape is
    /// already verified against `Tools/mu-analyze`, so going through it keeps
    /// the two reading the same thing by construction.
    /// Also hands back the `Summary` it computed along the way, so a caller
    /// that wants both (the `FLIP-RESULT` print and the tabs) can run the
    /// six-analysis session once instead of twice.
    static func analyzeFull(url: URL, lyricsNamed lyricsResource: String?)
        async throws -> (TrackAnalysis, Summary) {
        let s = try await analyze(url: url)
        // NOTE the shape. `analyze(url:)` encodes `SessionResult` directly, so
        // rhythm/structure/key sit at the TOP level here. The `result` wrapper,
        // and `durationSeconds` beside it, exist only in `Tools/mu-analyze`'s
        // output FILE, which adds them around the same payload. Reading
        // `root["result"]` in-app yields an empty dictionary and every array
        // below comes back empty — with no error, because every cast is
        // optional with a `?? [:]` fallback.
        let result = try JSONSerialization
            .jsonObject(with: s.jsonData) as? [String: Any] ?? [:]

        // CMTime encodes as {epoch, flags, timescale, value}; seconds are
        // value / timescale. Timescale is 44100 in practice but is read rather
        // than assumed, because a different source file could carry another.
        func seconds(_ any: Any?) -> Double? {
            guard let d = any as? [String: Any],
                  let v = d["value"] as? Double,
                  let ts = d["timescale"] as? Double, ts != 0 else { return nil }
            return v / ts
        }

        let rhythm = result["rhythm"] as? [String: Any] ?? [:]
        let barTimes = (rhythm["bars"] as? [[String: Any]] ?? [])
            .compactMap { seconds($0["start"] ?? $0) }
        let bars = barTimes.enumerated().map { Bar(idx: $0.offset, t: $0.element) }

        let structure = result["structure"] as? [String: Any] ?? [:]
        let sections = (structure["sections"] as? [[String: Any]] ?? [])
            .compactMap { row -> TrackSection? in
                guard let start = seconds(row["start"]),
                      let dur = seconds(row["duration"]) else { return nil }
                return TrackSection(start: start, end: start + dur)
            }

        var activity: [ActivitySample] = []
        let ia = result["instrumentActivity"] as? [String: Any] ?? [:]
        // Cast each instrument's rows individually rather than the whole
        // dictionary as `[String: [[String: Any]]]` in one shot: a single
        // strict nested cast means one malformed instrument (or one
        // non-conforming row) fails the WHOLE cast and `?? [:]` silently
        // blanks all four lanes at once, not just the bad one.
        for (name, any) in (ia["activity"] as? [String: Any] ?? [:]) {
            let rows = any as? [[String: Any]] ?? []
            let parsed = rows.compactMap { row -> (Double, Double)? in
                guard let t = seconds(row["time"]),
                      let level = row["value"] as? Double else { return nil }
                return (t, level)
            }.sorted { $0.0 < $1.0 }
            for (i, p) in parsed.enumerated() {
                let end = i + 1 < parsed.count ? parsed[i + 1].0 : s.duration
                activity.append(ActivitySample(instrument: name, start: p.0,
                                               end: end, level: p.1))
            }
        }

        var lyrics: [LyricLine] = []
        if let name = lyricsResource,
           let lrc = Bundle.main.url(forResource: name, withExtension: "lrc"),
           let text = try? String(contentsOf: lrc, encoding: .utf8) {
            lyrics = TimedLyrics.parse(text)
        }

        let ta = TrackAnalysis(bpm: s.bpm, key: s.key, duration: s.duration,
                               bars: bars, sections: sections,
                               activity: activity, lyrics: lyrics)
        return (ta, s)
    }
}
