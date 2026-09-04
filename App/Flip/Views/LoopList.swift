import SwiftUI

/// Loop candidates, best first. Selecting one shades its span on the Analysis
/// tab, which is the whole point of them sharing an axis.
struct LoopList: View {
    let analysis: TrackAnalysis
    @Binding var selected: LoopCandidate?

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
                    if loop.id == selected?.id {
                        Image(systemName: "checkmark").foregroundStyle(.yellow)
                    }
                }
            }
            .buttonStyle(.plain)
        }
        .listStyle(.plain)
    }
}
