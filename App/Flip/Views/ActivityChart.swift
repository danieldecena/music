import Charts
import SwiftUI

/// Four stacked instrument lanes plotted against the bar grid.
///
/// The x axis is bars, not seconds, so even spacing means even musical time.
/// Section boundaries are vertical rules; the selected loop is a shaded span.
struct ActivityChart: View {
    let analysis: TrackAnalysis
    let selectedLoop: LoopCandidate?

    private let colors: [String: Color] = [
        "drum": .red, "bass": .orange, "other": .teal, "vocal": .purple,
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(analysis.instruments, id: \.self) { name in
                lane(name)
            }
        }
    }

    private func lane(_ name: String) -> some View {
        let samples = analysis.samples(for: name)
        let peak = analysis.peak(for: name)
        return VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(name.uppercased())
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundStyle(colors[name] ?? .gray)
                Spacer()
                Text(String(format: "peak %.2f", peak))
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            Chart {
                ForEach(samples.indices, id: \.self) { i in
                    AreaMark(
                        x: .value("Bar", analysis.grid.barAt(samples[i].start)),
                        y: .value("Level", samples[i].level)
                    )
                    .foregroundStyle((colors[name] ?? .gray).opacity(0.35))
                }
                ForEach(analysis.sections.indices, id: \.self) { i in
                    RuleMark(x: .value("Bar",
                                       analysis.grid.barAt(analysis.sections[i].start)))
                        .foregroundStyle(.secondary.opacity(0.4))
                        .lineStyle(StrokeStyle(lineWidth: 1))
                }
                if let loop = selectedLoop {
                    RectangleMark(
                        xStart: .value("From", analysis.grid.barAt(loop.start)),
                        xEnd: .value("To", analysis.grid.barAt(loop.end))
                    )
                    .foregroundStyle(.yellow.opacity(0.22))
                }
            }
            .chartYScale(domain: 0...1)
            .chartXScale(domain: analysis.grid.firstBar...max(analysis.grid.lastBar,
                                                             analysis.grid.firstBar + 1))
            .chartYAxis(.hidden)
            .frame(height: 54)
        }
    }
}
