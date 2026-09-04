import SwiftUI

struct ContentView: View {
    @State private var analysis: TrackAnalysis?
    @State private var error: String?
    @State private var running = false

    var body: some View {
        NavigationStack {
            Group {
                if let analysis {
                    TimelineTabs(analysis: analysis)
                } else {
                    Form {
                        Section("Bundled clip") {
                            Text("testclip.m4a").font(.system(.body, design: .monospaced))
                            Button(running ? "Analyzing..." : "Analyze") { run() }
                                .disabled(running)
                        }
                        if let error {
                            Section("Error") {
                                Text(error).foregroundStyle(.red)
                                    .font(.system(.footnote, design: .monospaced))
                            }
                        }
                    }
                }
            }
            .navigationTitle("Flip")
            // Runs once on appear so a headless simulator or device launch
            // produces the FLIP-RESULT line without needing a tap.
            .task { if analysis == nil && !running { run() } }
        }
    }

    private func run() {
        guard let url = Bundle.main.url(forResource: "testclip", withExtension: "m4a")
        else { error = "testclip.m4a missing from the bundle"; return }
        running = true
        error = nil
        Task {
            do {
                let (full, s) = try await Runner.analyzeFull(url: url, lyricsNamed: "testclip")
                // Also to stdout, so a simulator or device run can be read back
                // with `simctl launch --console` instead of off a screenshot.
                print("FLIP-RESULT bpm=\(s.bpm) beats=\(s.beats) bars=\(s.bars) "
                      + "sections=\(s.sections) segments=\(s.segments) "
                      + "phrases=\(s.phrases) key=\(s.key) "
                      + "instruments=\(s.instruments.joined(separator: "/")) "
                      + "elapsed=\(s.elapsed) bytes=\(s.jsonBytes)")
                analysis = full
            }
            catch { self.error = "\(error)" }
            running = false
        }
    }
}
