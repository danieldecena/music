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
}
