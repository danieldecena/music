import SwiftUI

/// The tracks the Mac published into the container.
struct LibraryView: View {
    let documents: URL

    @State private var tracks: [PublishedTrack] = []
    @State private var loaded = false
    // A box, because `sheet(item:)` needs Identifiable and TrackAnalysis is
    // a value the analysis layer owns -- not somewhere to bolt an id on for
    // one view's presentation mechanics.
    private struct Opened: Identifiable { let id = UUID(); let analysis: TrackAnalysis }
    @State private var opened: Opened?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                if !loaded {
                    // Distinct from the empty case below: a scan still running
                    // and a container with nothing in it are different answers.
                    Text("reading...").foregroundStyle(.secondary)
                } else if tracks.isEmpty {
                    Section {
                        Text("No tracks published yet")
                        Text("publish_to_icloud <track>, on the Mac")
                            .font(.system(.footnote, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                }
                ForEach(tracks) { t in
                    Button { open(t) } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(t.name)
                            Text(t.analysis == nil
                                 ? "\(t.stems.count) stems, no analysis.json"
                                 : "\(t.stems.count) stems")
                                .font(.footnote)
                                .foregroundStyle(t.analysis == nil ? .orange : .secondary)
                        }
                    }
                    .disabled(t.analysis == nil)
                }
                if let error {
                    Section("Error") {
                        Text(error).foregroundStyle(.red)
                            .font(.system(.footnote, design: .monospaced))
                    }
                }
            }
            .navigationTitle("Library")
            .sheet(item: $opened) { o in NavigationStack { TimelineTabs(analysis: o.analysis) } }
            .task {
                tracks = LibraryIndex.tracks(inDocuments: documents)
                loaded = true
                print("FLIP-LIBRARY \(tracks.count) tracks at \(documents.path)")
            }
        }
    }

    private func open(_ t: PublishedTrack) {
        guard let json = t.analysis else { return }
        error = nil
        do { opened = Opened(analysis: try PublishedAnalysis.load(json)) }
        catch { self.error = "\(error)" }
    }
}
