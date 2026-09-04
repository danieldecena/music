import SwiftUI

struct ContentView: View {
    @State private var analysis: TrackAnalysis?
    @State private var error: String?
    @State private var running = false
    @State private var icloud: ContainerStatus?
    @State private var showLibrary = false

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
                        Section("iCloud") {
                            // Rendered as unknown until the claim returns, never
                            // as absent -- a claim still in flight and a device
                            // with no account are different answers.
                            Text(icloud?.label ?? "claiming...")
                                .font(.system(.footnote, design: .monospaced))
                                .foregroundStyle(icloud == .claimFailed ? .red : .secondary)
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
            // A toolbar entry rather than a new root, so the bundled-clip run
            // that the device smoke test reads stays exactly as it was.
            .toolbar {
                if case .ready = icloud {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Library") { showLibrary = true }
                    }
                }
            }
            .sheet(isPresented: $showLibrary) {
                if case .ready(let docs) = icloud { LibraryView(documents: docs) }
            }
            // Runs once on appear so a headless simulator or device launch
            // produces the FLIP-RESULT line without needing a tap.
            .task { if analysis == nil && !running { run() } }
            // Separate from `run()`: claiming the container is what makes the
            // directory exist for this iCloud account, and it has to happen
            // whether or not the bundled clip analyzes.
            .task {
                guard icloud == nil else { return }
                let s = await ICloudLibrary.claim()
                print("FLIP-ICLOUD \(s.label)")
                icloud = s
            }
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
