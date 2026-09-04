import Foundation

/// One timestamped lyric line. `end` is the next line's start, so a gap between
/// sung phrases belongs to the line before it. The last line has no end: the
/// parser reads a lyrics file and has no way to know the track's duration.
struct LyricLine: Equatable, Identifiable {
    let start: Double
    let end: Double?
    let text: String
    var id: String { "\(start)-\(text)" }
}

/// Port of `Scripts/lyrics.py:timed_lrc`. Kept separate from any plain-text
/// path for the same reason the Python is: the mix report wants a word set with
/// the timing removed, and this wants the timing.
enum TimedLyrics {
    // A metadata tag is [ar:...], [ti:...]. A timestamp is [mm:ss] with 1-3
    // optional decimals — sources differ, and all three occur in the wild.
    private static let stamp = try! NSRegularExpression(
        pattern: #"\[(\d{1,2}):(\d{2}(?:\.\d{1,3})?)\]"#)
    private static let meta = try! NSRegularExpression(
        pattern: #"^\[[a-zA-Z]+:[^\]]*\]$"#)

    static func parse(_ text: String) -> [LyricLine] {
        var rows: [(Double, String)] = []

        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty { continue }
            let whole = NSRange(line.startIndex..., in: line)
            if meta.firstMatch(in: line, range: whole) != nil { continue }

            let matches = stamp.matches(in: line, range: whole)
            if matches.isEmpty { continue }

            // The body is whatever is left once every stamp is removed. Taking
            // the text after the LAST stamp would be wrong for a line whose
            // stamps are not contiguous.
            var body = line
            for m in matches.reversed() {
                if let r = Range(m.range, in: body) { body.removeSubrange(r) }
            }
            body = body.trimmingCharacters(in: .whitespaces)
            if body.isEmpty { continue }

            for m in matches {
                guard let mm = Range(m.range(at: 1), in: line),
                      let ss = Range(m.range(at: 2), in: line),
                      let minutes = Double(line[mm]),
                      let seconds = Double(line[ss]) else { continue }
                rows.append((minutes * 60 + seconds, body))
            }
        }

        rows.sort { $0.0 < $1.0 }
        return rows.enumerated().map { i, row in
            LyricLine(start: row.0,
                      end: i + 1 < rows.count ? rows[i + 1].0 : nil,
                      text: row.1)
        }
    }
}
