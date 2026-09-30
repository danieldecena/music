import Foundation

/// A track directory the Mac published into the container, as the browser sees it.
struct PublishedTrack: Identifiable, Equatable {
    let name: String
    let folder: URL
    /// nil when the folder holds stems but no `analysis.json`. Listed anyway,
    /// so a partial publish reads as partial rather than disappearing.
    let analysis: URL?
    let stems: [URL]

    var id: String { name }
}

enum LibraryIndex {
    /// Matches `publish_to_icloud`, which writes `Tracks/<track>/`.
    static let tracksDirectory = "Tracks"

    /// Every published track under a container's `Documents`, by name.
    ///
    /// A missing `Tracks/` directory returns empty, which is the honest answer
    /// for a container nothing has published into yet -- distinct from a failed
    /// read, which cannot happen here: `contentsOfDirectory` throwing is caught
    /// and surfaces as empty only after the directory itself is known to exist.
    static func tracks(inDocuments docs: URL,
                       fileManager fm: FileManager = .default) -> [PublishedTrack] {
        let root = docs.appending(path: tracksDirectory)
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: root.path, isDirectory: &isDir), isDir.boolValue
        else { return [] }

        let folders = (try? fm.contentsOfDirectory(at: root,
                                                   includingPropertiesForKeys: [.isDirectoryKey],
                                                   options: [.skipsHiddenFiles])) ?? []
        return folders.compactMap { folder -> PublishedTrack? in
            var d: ObjCBool = false
            guard fm.fileExists(atPath: folder.path, isDirectory: &d), d.boolValue
            else { return nil }
            let files = (try? fm.contentsOfDirectory(at: folder,
                                                     includingPropertiesForKeys: nil,
                                                     options: [.skipsHiddenFiles])) ?? []
            let json = files.first { $0.lastPathComponent == "analysis.json" }
            let stems = files.filter { $0.pathExtension.lowercased() == "wav" }
                .sorted { $0.lastPathComponent < $1.lastPathComponent }
            return PublishedTrack(name: folder.lastPathComponent, folder: folder,
                                  analysis: json, stems: stems)
        }
        .sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
    }
}

enum PublishedAnalysis {
    enum Failure: Error, CustomStringConvertible {
        case notAWrappedResult(String)
        case noDuration(String)

        var description: String {
            switch self {
            case .notAWrappedResult(let n):
                return "\(n): no top-level `result` object -- this is not a Tools/mu-analyze file"
            case .noDuration(let n):
                return "\(n): no `durationSeconds` -- the last activity sample cannot be closed"
            }
        }
    }

    /// Reads a track the Mac published.
    ///
    /// The unwrap is the load-bearing line. `Tools/mu-analyze` writes
    /// `{analysisSeconds, durationSeconds, path, result}` around the same
    /// payload the app encodes bare, and every cast below a wrong root is
    /// optional with an empty fallback -- so reading the top level here would
    /// produce a track with zero bars, zero sections and no error at all.
    /// Hence `guard ... else throw` rather than `?? [:]`.
    static func load(_ url: URL) throws -> TrackAnalysis {
        let data = try Data(contentsOf: url)
        let root = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        let name = url.deletingLastPathComponent().lastPathComponent
        guard let result = root["result"] as? [String: Any] else {
            throw Failure.notAWrappedResult(name)
        }
        // Not defaulted to 0: duration closes the final activity sample, and a
        // zero would silently truncate the last lane segment to nothing.
        guard let duration = root["durationSeconds"] as? Double else {
            throw Failure.noDuration(name)
        }
        // No lyrics: `publish_to_icloud` copies stems and analysis.json only.
        return try Runner.assemble(result,
                                   summary: Runner.summarize(result, duration: duration),
                                   lyrics: [])
    }
}
