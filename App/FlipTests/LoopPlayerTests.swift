import AVFAudio
import Testing
@testable import Flip

@Suite("Loop player frame maths")
struct LoopPlayerTests {
    let loop = LoopCandidate(startBar: 4, start: 8.0, end: 16.0, nBars: 4,
                             score: 1.0, instruments: [:])

    @Test("seconds convert to frames at the file's sample rate")
    func converts() {
        let r = try! #require(LoopPlayer.frames(for: loop, sampleRate: 44100,
                                                totalFrames: 44100 * 30))
        #expect(r.start == 352800)        // 8.0s * 44100
        #expect(r.length == 352800)       // 8.0s span
    }

    @Test("a different sample rate scales both ends")
    func otherRate() {
        let r = try! #require(LoopPlayer.frames(for: loop, sampleRate: 48000,
                                                totalFrames: 48000 * 30))
        #expect(r.start == 384000)
        #expect(r.length == 384000)
    }

    @Test("a loop running past the end is clipped, not refused")
    func clips() {
        // 25s of audio, a loop asking for 8.0-16.0 is fine; asking past the end
        // must shorten rather than read out of bounds.
        let late = LoopCandidate(startBar: 0, start: 20.0, end: 30.0, nBars: 4,
                                 score: 1.0, instruments: [:])
        let r = try! #require(LoopPlayer.frames(for: late, sampleRate: 44100,
                                                totalFrames: 44100 * 25))
        #expect(r.start == 882000)
        #expect(r.length == 220500)       // 5s left, not the 10s asked for
    }

    @Test("a loop starting past the end of the file returns nil")
    func pastEnd() {
        let gone = LoopCandidate(startBar: 0, start: 40.0, end: 48.0, nBars: 4,
                                 score: 1.0, instruments: [:])
        #expect(LoopPlayer.frames(for: gone, sampleRate: 44100,
                                  totalFrames: 44100 * 30) == nil)
    }

    @Test("a zero-length loop returns nil rather than scheduling silence")
    func zeroLength() {
        let empty = LoopCandidate(startBar: 0, start: 5.0, end: 5.0, nBars: 4,
                                  score: 1.0, instruments: [:])
        #expect(LoopPlayer.frames(for: empty, sampleRate: 44100,
                                  totalFrames: 44100 * 30) == nil)
    }

    // MARK: - Offline, deterministic replacement for a "plug in a device and
    // listen" step.
    //
    // The plan's original Step 6 asked for a human ear on hardware. There is
    // no device attached to this run, so instead: render the engine through
    // `AVAudioEngine`'s manual (offline) rendering mode and inspect the
    // actual samples it produced. `isPlaying == true` alone is not evidence —
    // a running transport over silence is exactly the failure this catches.

    /// Locates the bundled clip via the *test host's* bundle. FlipTests runs
    /// hosted inside Flip.app (`TEST_HOST` in project.pbxproj), so
    /// `Bundle.main` here is the same bundle `LoopList.swift`'s `.task` reads.
    private func clipURL() throws -> URL {
        try #require(Bundle.main.url(forResource: "testclip", withExtension: "m4a"))
    }

    /// Writes a short, lossless sine-wave WAV to a temp file and returns its
    /// URL.
    ///
    /// The drift test needs this instead of the bundled AAC clip: decoding
    /// the identical compressed frame range twice through `AVAudioFile` is
    /// NOT bit-reproducible (confirmed empirically — repeat-vs-repeat samples
    /// differ by up to full-scale amplitude even with no scheduling bug at
    /// all). That is AAC decode noise, not scheduler drift, and it would
    /// swamp the thing this test exists to catch. A lossless PCM fixture
    /// removes that confound so the assertion is actually about the
    /// scheduler.
    private func synthURL() throws -> URL {
        let sr = 44100.0
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("flip-loopplayer-synth-\(UUID().uuidString).wav")
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: sr,
            AVNumberOfChannelsKey: 2,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsNonInterleaved: false,
        ]
        // Scoped so the AVAudioFile deallocates (flushing its header) before
        // this function returns — reading it back immediately otherwise sees
        // a zero-length file.
        func write() throws {
            let outFile = try AVAudioFile(forWriting: url, settings: settings,
                                          commonFormat: .pcmFormatInt16, interleaved: true)
            let totalFrames = AVAudioFrameCount(sr * 2.0)
            let buffer = try #require(AVAudioPCMBuffer(pcmFormat: outFile.processingFormat,
                                                        frameCapacity: totalFrames))
            buffer.frameLength = totalFrames
            let data = try #require(buffer.int16ChannelData)
            for i in 0..<Int(totalFrames) {
                let v = Int16(sin(2.0 * .pi * 440.0 * Double(i) / sr) * 16000.0)
                data[0][i * 2] = v
                data[0][i * 2 + 1] = v
            }
            try outFile.write(from: buffer)
        }
        try write()
        return url
    }

    /// Switches `engine` into offline manual-rendering mode. Must run before
    /// `play(_:)` starts the engine, since `enableManualRenderingMode`
    /// requires a stopped engine and `play` is what calls `engine.start()`.
    @MainActor
    private func enableOfflineRendering(_ engine: LoopEngine,
                                        format: AVAudioFormat) throws {
        engine.engine.stop()
        try engine.engine.enableManualRenderingMode(.offline, format: format,
                                                     maximumFrameCount: 4096)
    }

    /// Pulls `frames` sample frames from an already-running manual-rendering
    /// `engine` and returns channel 0's float samples.
    @MainActor
    private func renderOffline(_ engine: LoopEngine, frames: AVAudioFrameCount,
                               format: AVAudioFormat) throws -> [Float] {
        var out: [Float] = []
        out.reserveCapacity(Int(frames))
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format,
                                            frameCapacity: 4096) else {
            Issue.record("could not allocate render buffer")
            return []
        }
        var remaining = frames
        while remaining > 0 {
            let chunk = min(remaining, buffer.frameCapacity)
            let status = try engine.engine.renderOffline(chunk, to: buffer)
            #expect(status == .success)
            let n = Int(buffer.frameLength)
            if let ch = buffer.floatChannelData {
                out.append(contentsOf: UnsafeBufferPointer(start: ch[0], count: n))
            }
            remaining -= AVAudioFrameCount(n)
            if n == 0 { break } // avoid an infinite loop if rendering stalls
        }
        return out
    }

    @Test("the rendered loop is actually audible, not a silent transport")
    @MainActor
    func nonZeroRMS() throws {
        let url = try clipURL()
        let engine = LoopEngine()
        try engine.load(url: url)
        let file = try AVAudioFile(forReading: url)

        // A short, real window well inside the 30s clip.
        let loop = LoopCandidate(startBar: 0, start: 2.0, end: 2.2, nBars: 1,
                                 score: 1.0, instruments: [:])
        let range = try #require(LoopPlayer.frames(for: loop,
                                                    sampleRate: file.processingFormat.sampleRate,
                                                    totalFrames: file.length))

        try enableOfflineRendering(engine, format: file.processingFormat)
        try engine.play(loop, repeats: 3)

        let totalFrames = range.length * 3
        let samples = try renderOffline(engine, frames: totalFrames,
                                        format: file.processingFormat)
        #expect(samples.count == Int(totalFrames))

        let sumSquares = samples.reduce(0.0) { $0 + Double($1) * Double($1) }
        let rms = (sumSquares / Double(samples.count)).squareRoot()
        #expect(rms > 0.0001, "rendered RMS \(rms) is indistinguishable from silence")
    }

    @Test("repeat N begins at exactly N * length frames, not drifted")
    @MainActor
    func repeatsDoNotDrift() throws {
        let url = try synthURL()
        let engine = LoopEngine()
        try engine.load(url: url)
        let file = try AVAudioFile(forReading: url)

        let loop = LoopCandidate(startBar: 0, start: 0.5, end: 0.6, nBars: 1,
                                 score: 1.0, instruments: [:])
        let range = try #require(LoopPlayer.frames(for: loop,
                                                    sampleRate: file.processingFormat.sampleRate,
                                                    totalFrames: file.length))
        let length = Int(range.length)
        let repeats = 5

        try enableOfflineRendering(engine, format: file.processingFormat)
        try engine.play(loop, repeats: repeats)

        let samples = try renderOffline(engine, frames: AVAudioFrameCount(length * repeats),
                                        format: file.processingFormat)
        // `try #require` rather than `#expect`: a short render must stop the
        // test here, not fall through into `samples[base + k]` below and trap
        // out of bounds, taking the whole process down instead of failing
        // one test.
        try #require(samples.count == length * repeats)

        // Repeat 0 carries the varispeed unit's own warm-up transient — its
        // internal state is empty before any audio has passed through it, an
        // artifact of the effect itself, not the scheduler (confirmed: it
        // differs from every later repeat by a similar margin regardless of
        // scheduling). Repeats 1 and up are past that transient, so a
        // drift-free scheduler reproduces the exact same samples at every one
        // of their boundaries. If the loop had drifted (e.g. accumulated a
        // fractional frame per iteration, as `.loops` does), repeat N would
        // not line up sample-for-sample with repeat N-1.
        for n in 2..<repeats {
            let base = n * length
            let prevBase = (n - 1) * length
            var mismatches = 0
            for k in 0..<length {
                if samples[base + k] != samples[prevBase + k] { mismatches += 1 }
            }
            #expect(mismatches == 0,
                    "repeat \(n) diverged from repeat \(n - 1) at \(mismatches)/\(length) frames — loop point drifted")
        }
    }
}
