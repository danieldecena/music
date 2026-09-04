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
        // A fresh launch had nothing shaded on the Analysis tab: the loop
        // review that reported yellow rectangles across all four lanes was
        // reading a stale selection left over from a previous session's tap,
        // not this view's default state. Select the best-scored loop so the
        // chart has something shaded from the very first frame.
        .onAppear {
            if selectedLoop == nil {
                selectedLoop = analysis.loops.first
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
