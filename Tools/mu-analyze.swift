// Phase 0 probe: dump MusicUnderstanding's analysis of one audio file as JSON.
//
// Build: swiftc -parse-as-library -O -o Tools/mu-analyze Tools/mu-analyze.swift
// Run:   Tools/mu-analyze <audio file> [-o out.json]
//
// A CLI rather than an Xcode app on purpose: no project, no signing, no
// simulator, and it runs against the real library immediately. SessionResult is
// Encodable, so the whole analysis serializes without hand-written mapping.

import AVFoundation
import Foundation
import MusicUnderstanding

struct Envelope: Encodable {
    let path: String
    let durationSeconds: Double
    let analysisSeconds: Double
    let result: MusicUnderstandingSession.SessionResult
}

@main
struct MUAnalyze {
    static func die(_ msg: String) -> Never {
        FileHandle.standardError.write("mu-analyze: \(msg)\n".data(using: .utf8)!)
        exit(1)
    }

    static func main() async {
        let args = CommandLine.arguments
        guard args.count >= 2 else {
            FileHandle.standardError.write(
                "usage: mu-analyze <audio file> [-o out.json]\n".data(using: .utf8)!)
            exit(2)
        }

        let url = URL(fileURLWithPath: args[1])
        guard FileManager.default.fileExists(atPath: url.path) else {
            die("no such file: \(url.path)")
        }
        var outPath: String?
        if let i = args.firstIndex(of: "-o"), i + 1 < args.count { outPath = args[i + 1] }

        do {
            let asset = AVURLAsset(url: url)
            let duration = try await asset.load(.duration).seconds

            let session = try await MusicUnderstandingSession(asset: asset)
            let types: Set<AnalysisType> = [
                .rhythm, .key, .structure, .loudness, .pace, .instrumentActivity,
            ]

            let started = Date()
            let result = try await session.analyze(for: types)
            let elapsed = Date().timeIntervalSince(started)

            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            // Loudness reports -inf LUFS for digital silence, which JSON cannot
            // represent. Encode as strings rather than losing the frame.
            encoder.nonConformingFloatEncodingStrategy = .convertToString(
                positiveInfinity: "inf", negativeInfinity: "-inf", nan: "nan")
            let data = try encoder.encode(
                Envelope(
                    path: url.path, durationSeconds: duration,
                    analysisSeconds: elapsed, result: result))

            if let outPath {
                try data.write(to: URL(fileURLWithPath: outPath))
                FileHandle.standardError.write(
                    "wrote \(data.count) bytes to \(outPath) in \(String(format: "%.1f", elapsed))s\n"
                        .data(using: .utf8)!)
            } else {
                FileHandle.standardOutput.write(data)
                FileHandle.standardOutput.write("\n".data(using: .utf8)!)
            }
        } catch {
            die("\(error)")
        }
    }
}
