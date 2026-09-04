import AVFAudio
import Foundation
import Observation

struct FrameRange: Equatable {
    let start: AVAudioFramePosition
    let length: AVAudioFrameCount
}

enum LoopPlayer {
    /// The frame range a loop occupies in a file at `sampleRate`.
    ///
    /// Clipped to the file rather than refused, because the last scored window
    /// can reach one bar past the final downbeat — that is a real loop, just a
    /// short one. Returns nil only when there is genuinely nothing to play.
    static func frames(for loop: LoopCandidate, sampleRate: Double,
                       totalFrames: AVAudioFramePosition) -> FrameRange? {
        guard sampleRate > 0, loop.end > loop.start else { return nil }
        let start = AVAudioFramePosition(loop.start * sampleRate)
        guard start < totalFrames else { return nil }
        let wanted = AVAudioFramePosition((loop.end - loop.start) * sampleRate)
        let available = totalFrames - start
        let length = min(wanted, available)
        guard length > 0 else { return nil }
        return FrameRange(start: start, length: AVAudioFrameCount(length))
    }
}

/// Plays one loop, repeating, at an optional rate.
///
/// Each repeat is scheduled by hand rather than with `AVAudioPlayerNode`'s
/// `.loops` option: built-in looping accumulates floating-point drift, so the
/// loop walks off the beat over repeats. Apple's own clip-launcher sample
/// avoids it for the same reason.
@Observable
@MainActor
final class LoopEngine {
    // Internal rather than private so LoopPlayerTests can drive
    // AVAudioEngine's manual (offline) rendering mode directly — the brief's
    // sample code had these `private`. This does widen the class's surface:
    // anything in the app target can now call `engine.stop()` or push
    // buffers to `player` directly, bypassing `LoopEngine`'s own `stop()`
    // and desyncing `isPlaying` from the real transport (the same class of
    // bug `@Observable` alone doesn't prevent). No call site outside the
    // test target does this today, but nothing stops one from starting to.
    let engine = AVAudioEngine()
    let player = AVAudioPlayerNode()
    private let varispeed = AVAudioUnitVarispeed()
    private var file: AVAudioFile?
    private(set) var isPlaying = false

    init() {
        engine.attach(player)
        engine.attach(varispeed)
        engine.connect(player, to: varispeed, format: nil)
        engine.connect(varispeed, to: engine.mainMixerNode, format: nil)
    }

    func load(url: URL) throws {
        file = try AVAudioFile(forReading: url)
    }

    /// `rate` is a tempo multiple; 1.0 is the recording's own tempo. Varispeed
    /// moves pitch with rate, which is what a DJ pitch fader does. Use
    /// AVAudioUnitTimePitch instead when the key must not move.
    func play(_ loop: LoopCandidate, rate: Float = 1.0, repeats: Int = 8) throws {
        guard let file else { return }
        guard let range = LoopPlayer.frames(for: loop,
                                            sampleRate: file.processingFormat.sampleRate,
                                            totalFrames: file.length) else { return }
        stop()
        varispeed.rate = rate

        // Playback is the only audio here, so .playback with no options.
        // Configured before the engine starts, or the first buffer can be
        // routed before the category applies.
        try AVAudioSession.sharedInstance().setCategory(.playback)
        try AVAudioSession.sharedInstance().setActive(true)

        for _ in 0..<repeats {
            player.scheduleSegment(file, startingFrame: range.start,
                                   frameCount: range.length,
                                   at: nil, completionHandler: nil)
        }
        if !engine.isRunning { try engine.start() }
        player.play()
        isPlaying = true
    }

    func stop() {
        player.stop()
        isPlaying = false
    }
}
