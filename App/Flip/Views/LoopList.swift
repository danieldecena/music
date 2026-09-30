import SwiftUI

/// Loop candidates, best first. Selecting one shades its span on the Analysis
/// tab, which is the whole point of them sharing an axis.
struct LoopList: View {
    let analysis: TrackAnalysis
    @Binding var selected: LoopCandidate?
    @State private var engine = LoopEngine()
    @State private var loadError: String?

    var body: some View {
        List {
            // Surfaced the same way ContentView surfaces its own load
            // failure: a missing or zero-byte testclip.m4a (the Resources
            // README documents exactly this failure mode for a bad ffmpeg
            // invocation) used to leave `engine` fileless silently, so every
            // play tap did nothing with no visible reason why.
            if let loadError {
                Section("Error") {
                    Text(loadError).foregroundStyle(.red)
                        .font(.system(.footnote, design: .monospaced))
                }
            }
            ForEach(analysis.loops.prefix(12)) { loop in
                // The play/stop control is a sibling of the selection button
                // in this HStack, not nested inside its label — a Button
                // inside another Button's label is a known List hit-testing
                // hazard even with .buttonStyle(.plain) on both.
                HStack(spacing: 14) {
                    Button {
                        selected = loop
                    } label: {
                        HStack(spacing: 14) {
                            Text(String(format: "%.2f", loop.score))
                                .font(.system(.body, design: .monospaced))
                                .foregroundStyle(loop.id == selected?.id ? .yellow : .secondary)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Bars \(loop.startBar)–\(loop.startBar + loop.nBars - 1)")
                                    .font(.system(.body, design: .monospaced))
                                Text(String(format: "vocal %.2f · drum %.2f",
                                            loop.instruments["vocal"] ?? 0,
                                            loop.instruments["drum"] ?? 0))
                                    .font(.system(.caption2, design: .monospaced))
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .buttonStyle(.plain)

                    Spacer()

                    Button {
                        if engine.playingID == loop.id {
                            engine.stop()
                        } else {
                            selected = loop
                            try? engine.play(loop)
                        }
                    } label: {
                        Image(systemName: engine.playingID == loop.id
                              ? "stop.fill" : "play.fill")
                            .foregroundStyle(.yellow)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .listStyle(.plain)
        .task {
            guard let url = Bundle.main.url(forResource: "testclip", withExtension: "m4a") else {
                loadError = "testclip.m4a missing from the bundle"
                return
            }
            do {
                try engine.load(url: url)
            } catch {
                loadError = "\(error)"
            }
        }
    }
}
