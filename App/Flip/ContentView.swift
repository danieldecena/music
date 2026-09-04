import SwiftUI

struct ContentView: View {
    @State private var summary: Summary?
    @State private var error: String?
    @State private var running = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Bundled clip") {
                    Text("testclip.m4a").font(.system(.body, design: .monospaced))
                    Button(running ? "Analyzing..." : "Analyze") { run() }
                        .disabled(running)
                }
                if let s = summary {
                    Section("Rhythm") {
                        row("BPM", String(format: "%.3f", s.bpm))
                        row("beats", "\(s.beats)")
                        row("bars", "\(s.bars)")
                    }
                    Section("Structure") {
                        row("sections", "\(s.sections)")
                        row("segments", "\(s.segments)")
                        row("phrases", "\(s.phrases)")
                    }
                    Section("Other") {
                        row("key", s.key)
                        row("instruments", s.instruments.joined(separator: ", "))
                        row("elapsed", String(format: "%.1fs", s.elapsed))
                        row("json", "\(s.jsonBytes) bytes")
                    }
                }
                if let error {
                    Section("Error") {
                        Text(error).foregroundStyle(.red)
                            .font(.system(.footnote, design: .monospaced))
                    }
                }
            }
            .navigationTitle("Flip")
            // Runs once on appear so a headless simulator or device launch
            // produces the FLIP-RESULT line without needing a tap.
            .task { if summary == nil && !running { run() } }
        }
    }

    private func row(_ k: String, _ v: String) -> some View {
        HStack {
            Text(k).foregroundStyle(.secondary)
            Spacer()
            Text(v).font(.system(.body, design: .monospaced))
        }
    }

    private func run() {
        guard let url = Bundle.main.url(forResource: "testclip", withExtension: "m4a")
        else { error = "testclip.m4a missing from the bundle"; return }
        running = true
        error = nil
        Task {
            do {
                let s = try await Runner.analyze(url: url)
                // Also to stdout, so a simulator or device run can be read back
                // with `simctl launch --console` instead of off a screenshot.
                print("FLIP-RESULT bpm=\(s.bpm) beats=\(s.beats) bars=\(s.bars) "
                      + "sections=\(s.sections) segments=\(s.segments) "
                      + "phrases=\(s.phrases) key=\(s.key) "
                      + "instruments=\(s.instruments.joined(separator: "/")) "
                      + "elapsed=\(s.elapsed) bytes=\(s.jsonBytes)")
                summary = s
            }
            catch { self.error = "\(error)" }
            running = false
        }
    }
}
