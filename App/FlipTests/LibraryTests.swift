import Foundation
import Testing
@testable import Flip

/// Builds a container's `Documents` on disk, so the index is exercised against
/// a real filesystem rather than a stubbed one -- the thing it actually reads.
private struct Fixture: ~Copyable {
    let documents: URL
    init() throws {
        documents = URL(filePath: NSTemporaryDirectory())
            .appending(path: "flip-lib-\(UUID().uuidString)")
            .appending(path: "Documents")
        try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
    }
    func track(_ name: String, stems: [String], analysis: String?) throws -> URL {
        let dir = documents.appending(path: "Tracks").appending(path: name)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        for s in stems {
            try Data().write(to: dir.appending(path: s))
        }
        if let analysis {
            try analysis.write(to: dir.appending(path: "analysis.json"),
                               atomically: true, encoding: .utf8)
        }
        return dir
    }
    deinit {
        try? FileManager.default.removeItem(at: documents.deletingLastPathComponent())
    }
}

/// One bar, one section, one activity sample, in the file shape
/// `Tools/mu-analyze` writes: the payload wrapped in `result`, with
/// `durationSeconds` beside it.
private func wrappedJSON(bpm: Double = 120) -> String {
    """
    {"analysisSeconds": 1.0, "durationSeconds": 8.0, "path": "/x.m4a",
     "result": {
       "rhythm": {"beatsPerMinute": \(bpm),
                  "bars": [{"start": {"value": 0, "timescale": 44100}},
                           {"start": {"value": 88200, "timescale": 44100}}]},
       "structure": {"sections": [{"start": {"value": 0, "timescale": 44100},
                                   "duration": {"value": 352800, "timescale": 44100}}]},
       "key": {"ranges": [{"value": {"tonic": "d", "mode": "minor"}}]},
       "instrumentActivity": {"activity": {
         "drum":  [{"time": {"value": 0, "timescale": 44100}, "value": 0.9}],
         "bass":  [{"time": {"value": 0, "timescale": 44100}, "value": 0.5}],
         "other": [{"time": {"value": 0, "timescale": 44100}, "value": 0.3}],
         "vocal": [{"time": {"value": 0, "timescale": 44100}, "value": 0.1}]}}}}
    """
}

@Suite("Published library")
struct LibraryTests {
    @Test("a container with no Tracks directory lists nothing")
    func emptyContainer() throws {
        let f = try Fixture()
        #expect(LibraryIndex.tracks(inDocuments: f.documents).isEmpty)
    }

    @Test("published tracks are listed by name with their stems")
    func lists() throws {
        let f = try Fixture()
        _ = try f.track("02 Ivy", stems: ["vocals.wav", "drums.wav"], analysis: wrappedJSON())
        _ = try f.track("01 Nikes", stems: ["bass.wav"], analysis: wrappedJSON())
        let got = LibraryIndex.tracks(inDocuments: f.documents)
        #expect(got.map(\.name) == ["01 Nikes", "02 Ivy"])
        #expect(got[1].stems.map(\.lastPathComponent) == ["drums.wav", "vocals.wav"])
        #expect(got[0].analysis != nil)
    }

    @Test("a folder with stems but no analysis.json is listed, not dropped")
    func partialPublish() throws {
        let f = try Fixture()
        _ = try f.track("03 Pink + White", stems: ["drums.wav"], analysis: nil)
        let got = LibraryIndex.tracks(inDocuments: f.documents)
        #expect(got.count == 1)
        #expect(got[0].analysis == nil)
    }

    @Test("a published analysis decodes to the same geometry the tabs draw")
    func decodes() throws {
        let f = try Fixture()
        let dir = try f.track("02 Ivy", stems: [], analysis: wrappedJSON(bpm: 91))
        let a = try PublishedAnalysis.load(dir.appending(path: "analysis.json"))
        #expect(a.bpm == 91)
        #expect(a.key == "d minor")
        #expect(a.bars.count == 2)
        #expect(a.bars[1].t == 2.0)          // 88200 / 44100
        #expect(a.sections.count == 1)
        #expect(a.sections[0].end == 8.0)    // 352800 / 44100
        // The last sample is closed with durationSeconds, so a zero duration
        // would collapse it rather than run to the end of the track.
        #expect(a.peak(for: "drum") == 0.9)
        #expect(a.samples(for: "drum")[0].end == 8.0)
    }

    // The load-bearing one. `analyze(url:)` encodes the payload bare, the file
    // wraps it in `result`, and every cast under a wrong root is optional with
    // an empty fallback -- so reading the top level yields zero bars and no
    // error. This fails loudly if the unwrap is ever dropped.
    @Test("an unwrapped payload is refused rather than read as an empty track")
    func refusesUnwrapped() throws {
        let f = try Fixture()
        let bare = #"{"rhythm": {"beatsPerMinute": 120, "bars": []}}"#
        let dir = try f.track("04 Bare", stems: [], analysis: bare)
        #expect(throws: PublishedAnalysis.Failure.self) {
            try PublishedAnalysis.load(dir.appending(path: "analysis.json"))
        }
    }

    @Test("a wrapped payload with no durationSeconds is refused")
    func refusesNoDuration() throws {
        let f = try Fixture()
        let noDur = #"{"result": {"rhythm": {"beatsPerMinute": 120}}}"#
        let dir = try f.track("05 NoDur", stems: [], analysis: noDur)
        #expect(throws: PublishedAnalysis.Failure.self) {
            try PublishedAnalysis.load(dir.appending(path: "analysis.json"))
        }
    }
}
