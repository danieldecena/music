import SwiftUI

struct TimelineTabs: View {
    let analysis: TrackAnalysis
    @State private var selectedLoop: LoopCandidate?

    var body: some View {
        TabView {
            Tab("Analysis", systemImage: "waveform") {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        ActivityChart(analysis: analysis, selectedLoop: selectedLoop)
                    }
                    .padding()
                }
            }
            Tab("Lyrics", systemImage: "text.quote") {
                LyricsLane(analysis: analysis)
            }
            Tab("Loops", systemImage: "repeat") {
                LoopList(analysis: analysis, selected: $selectedLoop)
            }
        }
    }

    private var header: some View {
        HStack(spacing: 18) {
            stat("BPM", String(format: "%.1f", analysis.bpm))
            stat("KEY", analysis.key)
            stat("BARS", "\(analysis.bars.count)")
            stat("SECTIONS", "\(analysis.sections.count)")
        }
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(label).font(.system(.caption2, design: .monospaced))
                .foregroundStyle(.secondary)
            Text(value).font(.system(.title3, design: .monospaced))
        }
    }
}
