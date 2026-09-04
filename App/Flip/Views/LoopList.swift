import SwiftUI

/// Loop candidates, best first. Selecting one shades its span on the Analysis
/// tab, which is the whole point of them sharing an axis.
struct LoopList: View {
    let analysis: TrackAnalysis
    @Binding var selected: LoopCandidate?
    @State private var engine = LoopEngine()

    var body: some View {
        List(analysis.loops.prefix(12)) { loop in
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
                    Spacer()
                    Button {
                        if engine.isPlaying && loop.id == selected?.id {
                            engine.stop()
                        } else {
                            selected = loop
                            try? engine.play(loop)
                        }
                    } label: {
                        Image(systemName: engine.isPlaying && loop.id == selected?.id
                              ? "stop.fill" : "play.fill")
                            .foregroundStyle(.yellow)
                    }
                    .buttonStyle(.plain)
                }
            }
            .buttonStyle(.plain)
        }
        .listStyle(.plain)
        .task {
            if let url = Bundle.main.url(forResource: "testclip", withExtension: "m4a") {
                try? engine.load(url: url)
            }
        }
    }
}
