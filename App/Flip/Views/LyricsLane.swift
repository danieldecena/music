import SwiftUI

/// Lyric lines against the same bar grid the chart uses, so a line can be read
/// as "this happens at bar 47" rather than at a wall-clock time that means
/// nothing musically.
struct LyricsLane: View {
    let analysis: TrackAnalysis

    var body: some View {
        Group {
            if analysis.lyrics.isEmpty {
                ContentUnavailableView(
                    "No lyrics for this clip",
                    systemImage: "text.quote",
                    description: Text("Add a .lrc file beside the audio and rebuild.")
                )
            } else {
                List(analysis.lyrics) { line in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text("\(Int(analysis.grid.barAt(line.start)))")
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .frame(width: 34, alignment: .trailing)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(line.text)
                            Text(timestamp(line.start))
                                .font(.system(.caption2, design: .monospaced))
                                .foregroundStyle(.tertiary)
                        }
                    }
                }
                .listStyle(.plain)
            }
        }
    }

    private func timestamp(_ t: Double) -> String {
        String(format: "%d:%05.2f", Int(t) / 60, t.truncatingRemainder(dividingBy: 60))
    }
}
