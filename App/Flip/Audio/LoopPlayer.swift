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
    /// Clipped to the file rather than refused. NOT because a scored loop
    /// window can land past the final downbeat — `LoopScorer.score` only ever
    /// emits windows ending at an existing bar index. The real reason:
    /// converting a legitimate `loop.end` to frames at `sampleRate` can round
    /// to one frame past the file's actual `totalFrames`, and refusing an
    /// otherwise-valid loop over a sub-sample rounding difference would be
    /// worse than trimming it by one frame. Returns nil only when there is
    /// genuinely nothing to play.
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
    // and desyncing `playingID` from the real transport (the same class of
    // bug `@Observable` alone doesn't prevent). No call site outside the
    // test target does this today, but nothing stops one from starting to.
    let engine = AVAudioEngine()
    let player = AVAudioPlayerNode()
    private let varispeed = AVAudioUnitVarispeed()
    private var file: AVAudioFile?

    /// The `LoopCandidate.id` currently playing, or nil when nothing is.
    ///
    /// This used to be `isPlaying: Bool` — "is something playing" rather than
    /// "which loop is playing". That conflated every row's stop button with
    /// whichever loop actually had audio running (tapping another row's
    /// non-play area, which only updates `selected`, made THAT row look like
    /// the one playing). A row now compares its own `loop.id` against this
    /// instead of a single shared flag.
    ///
    /// Only `stop()` clears it: a loop repeats until it is stopped, so there
    /// is no natural completion for a handler to report.
    private(set) var playingID: Int?

    /// Bumped by `stop()` (including the implicit one at the top of `play()`)
    /// so a completion handler from an already-superseded `play()` call can
    /// tell it is stale and must not clear a NEWER `playingID`.
    private var playToken = 0

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
    /// `queued` is how many passes sit scheduled ahead of the playhead, not how
    /// many the loop plays: each one queues another as it finishes, so playback
    /// continues until `stop()`. A depth above 1 leaves slack for a completion
    /// handler that lands late; the default is the only value the app uses.
    /// Tests pass an explicit depth because a blocking offline render cannot
    /// let the MainActor top-up run.
    func play(_ loop: LoopCandidate, rate: Float = 1.0,
              queued: Int = LoopEngine.queuedSegments) throws {
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

        let token = playToken
        for _ in 0..<max(1, queued) {
            scheduleOnePass(file: file, range: range, token: token)
        }
        if !engine.isRunning { try engine.start() }
        player.play()
        playingID = loop.id
    }

    /// Number of passes queued ahead of the playhead by default.
    static let queuedSegments = 4

    /// Schedules one pass of the loop and queues another when it completes.
    ///
    /// Scheduling every repeat up front stops being an option once the count is
    /// unbounded, so the queue is kept shallow and topped up instead.
    private func scheduleOnePass(file: AVAudioFile, range: FrameRange, token: Int) {
        player.scheduleSegment(file, startingFrame: range.start,
                               frameCount: range.length, at: nil) { [weak self] in
            _ = Task { @MainActor in
                // A completion belonging to a superseded play() must not queue
                // audio against the loop that replaced it.
                guard let self, self.playToken == token else { return }
                self.scheduleOnePass(file: file, range: range, token: token)
            }
        }
    }

    func stop() {
        player.stop()
        playToken += 1
        playingID = nil
    }
}
